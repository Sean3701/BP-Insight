"""Deterministic mock workflow. Never calls an LLM or infers business facts."""
from dataclasses import dataclass
from typing import Protocol
from core.extraction.catalog import CATEGORIES, FIELD_CATALOG
from core.extraction.llm_contracts import DisabledExtractor, ExtractionInput

PIPELINE_VERSION = 'investment-mock-v1'
STEPS = (
    ('materials', '整理资料与来源'),
    ('extraction', '模拟提取接口'),
    ('checks', '检查记录与证据'),
    ('specialists', '汇总专业模块'),
    ('report', '生成演示报告'),
)

@dataclass(frozen=True)
class AnalysisContext:
    snapshot: dict
    intermediate: dict

class AnalysisModule(Protocol):
    def run(self, context: AnalysisContext) -> dict: ...

@dataclass(frozen=True)
class MockSpecialist:
    category: str

    def run(self, context: AnalysisContext) -> dict:
        definitions = [f for f in FIELD_CATALOG if f['category'] == self.category]
        fields = []
        for definition in definitions:
            records = [f for f in context.snapshot['facts'] if f['field_key'] == definition['key']]
            fields.append({**definition, 'records': records,
                           'state': 'recorded' if records else 'not_extracted'})
        return {'category': self.category, 'title': CATEGORIES[self.category],
                'mode': 'mock', 'judgment': None, 'fields': fields}


def run_step(key: str, snapshot: dict, intermediate: dict) -> dict:
    if key == 'materials':
        return {'documents': len(snapshot['documents']),
                'total_segments': snapshot['total_segments'],
                'included_segments': len(snapshot['sources']),
                'context_limited': snapshot['context_limited']}
    if key == 'extraction':
        # Empty by design; activating a real provider requires a separate change.
        candidates = DisabledExtractor().extract(ExtractionInput(
            project_id=snapshot['project']['id'], segments=snapshot['sources']))
        return {'mode': 'disabled_mock', 'candidates': candidates,
                'ai_extraction_performed': False, 'ai_review_performed': False}
    if key == 'checks':
        findings = []
        for doc in snapshot['documents']:
            if doc['status'] != 'processed' or not doc['segments']:
                findings.append({'kind': 'document_quality', 'field_key': None,
                    'message': f"文件「{doc['filename']}」未成功提取可用文字，需检查。",
                    'evidence': [], 'document_id': doc['id']})
        if snapshot['context_limited']:
            findings.append({'kind': 'context_limit', 'field_key': None,
                'message': '模拟输入仅包含部分片段，不代表已检查整份材料。', 'evidence': []})
        for definition in FIELD_CATALOG:
            records = [f for f in snapshot['facts'] if f['field_key'] == definition['key']]
            if not records:
                findings.append({'kind': 'record_gap', 'field_key': definition['key'],
                    'message': definition['label'] + '尚无结构化记录；当前尚未执行真实 AI 提取，不能据此判断 BP 未披露。',
                    'evidence': []})
            if len({f['value'] for f in records}) > 1:
                findings.append({'kind': 'different_values', 'field_key': definition['key'],
                    'message': definition['label'] + '存在不同记录值，需核对年份、币种和统计口径；不自动判定为事实矛盾。',
                    'evidence': [f['evidence'] for f in records]})
            for fact in records:
                if not fact['quote_matches']:
                    findings.append({'kind': 'quote_mismatch', 'field_key': definition['key'],
                        'message': definition['label'] + '的引文与当前来源不一致，需复核。',
                        'evidence': [fact['evidence']]})
        return {'method': 'deterministic_rules', 'semantic_review_performed': False, 'findings': findings}
    if key == 'specialists':
        context = AnalysisContext(snapshot, intermediate)
        return {'sections': [MockSpecialist(category).run(context) for category in CATEGORIES]}
    if key == 'report':
        questions = []
        labels = {f['key']: f['label'] for f in FIELD_CATALOG}
        for finding in intermediate['checks']['findings']:
            if finding['kind'] == 'record_gap':
                questions.append({'kind': 'template', 'field_key': finding['field_key'],
                    'question': f"请确认材料中是否包含「{labels[finding['field_key']]}」，并提供相应原文及时间口径。",
                    'evidence': []})
            elif finding['kind'] in ('different_values', 'quote_mismatch'):
                questions.append({'kind': 'template', 'field_key': finding['field_key'],
                    'question': finding['message'], 'evidence': finding['evidence']})
        return {
            'title': '项目分析流程演示报告', 'mode': 'mock',
            'notice': '模拟流程，非真实模型分析。未执行自动语义提取、AI审核或外部事实核验；不构成投资判断。',
            'pipeline_version': PIPELINE_VERSION, 'prompt_version': 'mock-template-v1',
            'provider': 'mock', 'model': 'disabled-mock', 'external_calls': 0,
            'project': snapshot['project'], 'materials': snapshot['documents'],
            'input_scope': intermediate['materials'],
            'ai_extraction_performed': False, 'ai_review_performed': False,
            'sections': intermediate['specialists']['sections'],
            'findings': intermediate['checks']['findings'], 'questions': questions,
            'scores': {'project_attractiveness': None, 'investment_risk': None, 'evidence_completeness': None},
            'source_preview': [{**s, 'content': s['content'][:240]} for s in snapshot['sources'][:3]],
            'snapshot_notice': '报告保存生成时的数据快照；后续修改记录不会改写历史报告，请重新运行生成新版。',
        }
    raise ValueError('Unknown pipeline step')
