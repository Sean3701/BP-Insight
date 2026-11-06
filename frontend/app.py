"""VC Intelligence Platform — M04D: user-facing navigation and developer diagnostics.
Existing FastAPI endpoints and persisted project/document data remain unchanged.
"""
import json
import os
import uuid
import urllib.error
import urllib.request

import streamlit as st

API_BASE = os.getenv('VC_API_BASE', 'http://127.0.0.1:8000').rstrip('/')
st.set_page_config(page_title='VC Intelligence Platform', page_icon='📊', layout='wide')


def api_request(path, method='GET', payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(API_BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def upload_bp(project_id, uploaded):
    boundary = 'vc' + uuid.uuid4().hex
    # Filename is only metadata; backend is responsible for sanitizing and storage.
    filename = uploaded.name.replace('"', '_').replace('\\', '_').replace('/', '_')
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode('utf-8') + uploaded.getvalue() + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    req = urllib.request.Request(f'{API_BASE}/api/projects/{project_id}/documents', data=body, method='POST',
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode('utf-8'))


def error_text(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP {exc.code}: ' + exc.read().decode('utf-8', errors='replace')[:500]
    return str(exc)


def project_label(p):
    return f"{p['name']} · #{p['id']}"


def list_docs(project_id):
    return api_request(f'/api/projects/{project_id}/documents')


def display_documents(docs):
    if not docs:
        st.info('该项目还没有上传 BP。')
        return
    for d in docs:
        status = d['status']
        with st.container(border=True):
            a, b = st.columns([4, 1])
            with a:
                st.markdown(f"**📄 {d['filename']}**")
                st.caption(f"{d['size_bytes'] / 1024 / 1024:.2f} MB · {d['segments']} 个原文片段 · 文件 #{d['id']}")
            with b:
                if status == 'processed':
                    st.success('解析完成', icon='✅')
                elif status == 'empty':
                    st.warning('未提取到文字')
                else:
                    st.error('解析失败')
            if d.get('warning'):
                st.warning('解析提示：' + d['warning'])
    st.caption('材料中的陈述尚未经过外部独立核验；图片、扫描文字和复杂图表可能无法完整提取。')


def project_selector(projects, key):
    if not projects:
        st.info('请先到「项目总览」创建一个投资项目。')
        return None
    ids = {p['id']: p for p in projects}
    chosen = st.selectbox('当前投资项目', options=list(ids), format_func=lambda x: project_label(ids[x]), key=key)
    return ids[chosen]


def dashboard(projects):
    st.header('项目总览')
    st.caption('集中管理投资项目与 BP 文件。')
    c1, c2 = st.columns(2)
    c1.metric('已创建项目', len(projects))
    c2.metric('分析流程', 'Mock 演示', help='支持模拟任务和报告保存，尚未执行真实 AI 分析')
    with st.expander('➕ 创建投资项目', expanded=not bool(projects)):
        with st.form('new_project', clear_on_submit=True):
            name = st.text_input('项目名称', placeholder='例如：示例 AI 创业公司')
            description = st.text_area('备注（可选）', height=80)
            submitted = st.form_submit_button('创建项目', type='primary')
            if submitted:
                if not name.strip():
                    st.warning('请填写项目名称。')
                else:
                    try:
                        api_request('/api/projects', 'POST', {'name': name, 'description': description})
                        st.success('项目创建成功。')
                        st.rerun()
                    except Exception as exc:
                        st.error('创建失败：' + error_text(exc))
    if projects:
        st.subheader('全部项目')
        st.dataframe([{'编号': p['id'], '项目名称': p['name'], '备注': p['description'], '创建时间': p['created_at']}
                      for p in projects], hide_index=True, use_container_width=True)
        st.info('选择左侧「项目工作台」，可为具体项目上传和管理 BP。')


REVIEW_LABELS = {'pending': '待人工审核', 'confirmed': '已人工审核', 'rejected': '已驳回'}


def project_overview(project_id):
    st.subheader('投资项目速览')
    try:
        overview = api_request(f'/api/projects/{project_id}/vc-overview')
    except Exception as exc:
        st.error('读取速览失败：' + error_text(exc))
        st.info('请确认已安装 M04A/M04B 后端，并停止旧服务后重新启动。')
        return
    summary = overview['summary']
    a, b = st.columns(2)
    a.metric('已有记录的字段', summary['with_candidates'])
    b.metric('档案字段总数', summary['catalog_fields'])
    st.caption('字段覆盖数量仅表示记录情况，不是投资评分，也不表示已核验。')
    st.info('尚未启用真实 AI 提取。可直接进入「分析任务」测试流程，无需先人工录入；如需校正，可使用「事实维护」。')
    for section in overview['sections']:
        with st.container(border=True):
            st.markdown('**' + section['title'] + '**')
            populated = [f for f in section['fields'] if f['state'] != 'missing']
            if not populated:
                st.caption('尚无相关记录')
            for field in populated:
                state = field['state']
                label = '存在不同口径，需复核' if state == 'potential_conflict' else ('已人工审核' if state == 'source_claim_reviewed' else '待人工审核')
                st.text(f"{field['label']}：{field['value']}")
                st.caption(f'{label} · 企业自述 · 未经外部核验')
                if field['has_conflict']:
                    st.warning('此字段有多条不同的已审核记录，当前只显示其中一条。请在「事实维护」查看全部记录并核对时间、币种与口径。')
                evidence = field.get('evidence')
                if evidence:
                    with st.expander('查看来源 · ' + field['label']):
                        st.text(evidence['document_name'] + ' · ' + evidence['location'])
                        st.text(evidence['quote'])
            missing = [f['label'] for f in section['fields'] if f['state'] == 'missing']
            if missing:
                st.caption('尚未录入：' + '、'.join(missing))
    st.caption(overview['notice'])


def fact_maintenance(project_id, docs):
    st.subheader('事实维护')
    st.caption('供资料录入与校正使用。人工审核表示引文与录入经过检查，不表示企业陈述真实。')
    try:
        fields = api_request('/api/extraction/fields')['fields']
        facts = api_request(f'/api/projects/{project_id}/facts')
    except Exception as exc:
        st.error('读取事实维护数据失败：' + error_text(exc))
        return
    with st.expander('新增有原文支持的记录', expanded=False):
        available = {d['id']: d for d in docs if d['segments'] > 0}
        if not available:
            st.info('请先在「项目文件」上传并解析资料。')
        else:
            docid = st.selectbox('来源文件', list(available), format_func=lambda i: available[i]['filename'], key=f'fact_doc_{project_id}')
            batches = max(1, (available[docid]['segments'] + 29) // 30)
            batch = st.number_input('原文批次（每批 30 条）', min_value=1, max_value=batches, value=1, key=f'fact_batch_{project_id}_{docid}')
            try:
                segments = api_request(f'/api/documents/{docid}/segments?offset={(batch-1)*30}&limit=30')['items']
            except Exception as exc:
                st.error('读取来源失败：' + error_text(exc))
                segments = []
            if segments:
                lookup = {x['id']: x for x in segments}
                sid = st.selectbox('来源片段', list(lookup), format_func=lambda i: f"{lookup[i]['location']} · #{i}", key=f'fact_segment_{project_id}_{docid}_{batch}')
                st.text(lookup[sid]['content'])
                with st.form(f'new_fact_{project_id}_{docid}_{sid}', clear_on_submit=True):
                    field = st.selectbox('档案字段', list(fields), format_func=lambda k: fields[k])
                    value = st.text_area('字段值', max_chars=3000)
                    quote = st.text_area('原文引文（从上方逐字复制）', max_chars=4000)
                    submit = st.form_submit_button('保存为待审核记录', type='primary')
                if submit:
                    if not value.strip() or not quote.strip():
                        st.warning('请填写字段值和原文引文。')
                    elif quote.strip() not in lookup[sid]['content']:
                        st.warning('引文必须逐字存在于所选来源片段中。')
                    else:
                        try:
                            api_request(f'/api/projects/{project_id}/facts', 'POST', {'segment_id': sid, 'field_key': field, 'value_text': value.strip(), 'evidence_quote': quote.strip()})
                            st.session_state['fact_flash'] = '记录已保存，状态为待人工审核。'
                            st.rerun()
                        except Exception as exc:
                            st.error('保存失败：' + error_text(exc))
    if 'fact_flash' in st.session_state:
        st.success(st.session_state.pop('fact_flash'))
    st.markdown('**已有记录**')
    state_filter = st.selectbox('审核状态筛选', ['all', 'pending', 'confirmed', 'rejected'], format_func=lambda x: '全部' if x == 'all' else REVIEW_LABELS[x], key=f'fact_filter_{project_id}')
    visible = [f for f in facts if state_filter == 'all' or f['review_status'] == state_filter]
    if not visible:
        st.info('当前没有符合条件的记录。')
    for fact in visible:
        with st.expander(f"#{fact['id']} · {fact['field_label']} · {REVIEW_LABELS.get(fact['review_status'], fact['review_status'])}"):
            st.text(fact['value_text'])
            document_name = next((d['filename'] for d in docs if d['id'] == fact['document_id']), f"文件 #{fact['document_id']}")
            st.caption(document_name + ' · ' + fact['location'])
            st.text(fact['evidence_quote'])
            st.caption('引文存在只证明它来自材料；请同时核对字段值是否受到引文支持。')
            with st.form(f"review_fact_{fact['id']}"):
                states = list(REVIEW_LABELS)
                state = st.selectbox('设置审核状态', states, index=states.index(fact['review_status']), format_func=lambda x: REVIEW_LABELS[x])
                note = st.text_area('审核备注', value=fact['reviewer_note'], max_chars=1000)
                reviewed = st.form_submit_button('保存审核状态')
            if reviewed:
                try:
                    api_request(f"/api/facts/{fact['id']}/review", 'PATCH', {'review_status': state, 'reviewer_note': note})
                    st.session_state['fact_flash'] = '审核状态已更新。'
                    st.rerun()
                except Exception as exc:
                    st.error('审核保存失败：' + error_text(exc))


def workspace(projects):
    st.header('项目工作台')
    project = project_selector(projects, 'workspace_project')
    if project is None:
        return
    st.caption('管理项目资料与结构化档案；所有 BP 陈述均未经外部独立核验。')
    section = st.radio('工作台视图', ['项目速览', '项目文件', '分析任务', '事实维护'], horizontal=True, key='workspace_view')
    if section == '项目速览':
        project_overview(project['id'])
        return
    if section == '分析任务':
        analysis_panel(project, allow_launch=True)
        return
    try:
        docs = list_docs(project['id'])
    except Exception as exc:
        st.error('无法读取项目文件：' + error_text(exc))
        return
    if section == '事实维护':
        fact_maintenance(project['id'], docs)
        return
    st.subheader('项目文件')
    display_documents(docs)
    st.subheader('上传新资料')
    uploaded = st.file_uploader('选择 PDF / PPTX / DOCX / XLSX（单文件最大 25 MB）',
                                type=['pdf', 'pptx', 'docx', 'xlsx'], key=f"bp_{project['id']}")
    if uploaded is not None:
        st.caption(f'待上传：{uploaded.name} · {uploaded.size / 1024 / 1024:.2f} MB')
        if st.button('上传并解析', type='primary', disabled=uploaded.size > 25 * 1024 * 1024):
            try:
                with st.spinner('正在本地保存并解析文件...'):
                    result = upload_bp(project['id'], uploaded)
                if result['status'] == 'processed':
                    st.success(f"上传成功，已提取 {result['segments']} 个原文片段。")
                else:
                    st.warning(f"已保存文件，解析状态：{result['status']}。{result.get('warning') or ''}")
                st.rerun()
            except Exception as exc:
                st.error('上传失败：' + error_text(exc))
    st.divider()
    st.subheader('投资分析')
    st.info('资料解析后，切换上方「分析任务」可发起 Mock 流程演示。无需先人工录入或审核。')


RUN_LABELS = {'queued': '等待执行', 'running': '正在执行', 'completed': '已完成', 'failed': '未完成'}


def show_report(report):
    st.subheader(report['title'])
    st.warning(report['notice'])
    a, b, c = st.columns(3)
    a.metric('关联资料', len(report['materials']))
    b.metric('真实 AI 提取', '未执行')
    c.metric('外部模型调用', report['external_calls'])
    st.caption('项目吸引力、投资风险、证据完备度均未评分。以下内容是资料快照、已有记录和规则模板。')
    if report['input_scope']['context_limited']:
        st.warning('模拟输入包含部分片段；尚未检查整份材料。')
    st.markdown('**项目要素 · 已有记录**')
    for section in report['sections']:
        with st.container(border=True):
            st.markdown('**' + section['title'] + '**')
            recorded = [f for f in section['fields'] if f['records']]
            if not recorded:
                st.caption('暂无结构化记录，尚未执行真实 AI 提取。')
            for field in recorded:
                for record in field['records']:
                    st.text(field['label'] + '：' + record['value'])
                    st.caption(REVIEW_LABELS.get(record['review_status'], record['review_status']) + ' · 企业自述 · 未经外部核验')
                    with st.expander('查看报告证据 · ' + field['label'] + f" · #{record['assertion_id']}"):
                        evidence = record['evidence']
                        st.text(evidence['document_name'] + ' · ' + evidence['location'])
                        st.text(evidence['quote'])
                        if not record['quote_matches']:
                            st.error('当前来源不再包含该引文，需复核。')
    st.markdown('**资料检查 · 固定规则**')
    gaps = [f for f in report['findings'] if f['kind'] == 'record_gap']
    issues = [f for f in report['findings'] if f['kind'] != 'record_gap']
    st.caption(f'尚无结构化记录的字段：{len(gaps)} 项。尚未执行 AI 提取，不能据此认定 BP 缺少信息。')
    if not issues:
        st.info('未触发当前固定检查规则；这不表示项目无风险，也不表示已通过 AI 审核。')
    for issue in issues:
        st.warning(issue['message'])
        if issue['evidence']:
            with st.expander('检查依据 · ' + issue['message']):
                for evidence in issue['evidence']:
                    st.text(evidence['document_name'] + ' · ' + evidence['location'])
                    st.text(evidence['quote'])
    with st.expander(f"追问清单 · {len(report['questions'])} 条固定模板（非 AI 建议）"):
        if report['questions']:
            st.dataframe([{'序号': i, '待确认问题': q['question']} for i, q in enumerate(report['questions'], 1)], hide_index=True, use_container_width=True)
        else:
            st.caption('未生成固定模板问题；不表示尽调已经完成。')
    with st.expander('关联材料与来源抽样'):
        for doc in report['materials']:
            st.text(doc['filename'])
            st.caption(f"片段数：{doc['segments']} · 解析状态：{doc['status']}")
        st.caption('下方最多三段原文摘录仅演示来源引用，不是 AI 提取或摘要。')
        names = {d['id']: d['filename'] for d in report['materials']}
        for source in report['source_preview']:
            st.text(names.get(source['document_id'], '原文件') + ' · ' + source['location'])
            st.text(source['content'])
    st.caption(report['snapshot_notice'])
    st.caption(f"流程版本：{report['pipeline_version']} · 模型：{report['model']} · 模板：{report['prompt_version']}")


def analysis_panel(project, allow_launch=False):
    project_id = project['id']
    st.caption('先跑通自动任务与报告，再接入真实模型测试能力。人工维护是可选校正入口。')
    st.warning('当前为 Mock 流程，不调用真实模型，不执行 AI 提取或语义审核。')
    try:
        runs = api_request(f'/api/projects/{project_id}/analysis-runs')
    except Exception as exc:
        st.error('读取任务失败：' + error_text(exc))
        st.info('请确认完整安装本次后端更新，并停止旧服务后重新启动。')
        return
    active = any(r['status'] in ('queued', 'running') for r in runs)
    if allow_launch:
        if st.button('运行模拟分析', type='primary', disabled=active, key=f'launch_analysis_{project_id}'):
            try:
                result = api_request(f'/api/projects/{project_id}/analysis-runs', 'POST', {'mode': 'mock'})
                st.session_state[f'report_run_{project_id}'] = result['id']
                st.rerun()
            except Exception as exc:
                st.error('任务未能创建：' + error_text(exc))
    if st.button('刷新任务状态', key=f'refresh_analysis_{project_id}'):
        st.rerun()
    if not runs:
        st.info('还没有分析任务。上传可解析的 BP 后，在「项目工作台 → 分析任务」发起模拟分析。')
        return
    lookup = {r['id']: r for r in runs}
    selection_key = f'report_run_{project_id}'
    if st.session_state.get(selection_key) not in lookup:
        st.session_state[selection_key] = next(iter(lookup))
    rid = st.selectbox('选择已保存的任务（最近100条）', list(lookup),
        format_func=lambda i: f"#{i} · {RUN_LABELS.get(lookup[i]['status'], lookup[i]['status'])} · Mock", key=selection_key)
    try:
        run = api_request(f'/api/analysis-runs/{rid}')
    except Exception as exc:
        st.error('读取任务详情失败：' + error_text(exc))
        return
    st.write('任务状态：' + RUN_LABELS.get(run['status'], run['status']))
    if run['status'] in ('queued', 'running'):
        st.info('任务正在后台执行，稍后点击「刷新任务状态」。')
    if run['status'] == 'failed':
        st.error(run['error'])
        st.caption('可以重新发起任务，原始资料与旧报告保留。')
    if run['steps']:
        with st.expander('查看执行步骤'):
            st.dataframe([{'步骤': step['title'], '状态': RUN_LABELS.get(step['status'], step['status'])} for step in run['steps']], hide_index=True, use_container_width=True)
    if run['status'] == 'completed' and run['report']:
        show_report(run['report'])
        st.download_button('下载演示报告 JSON', data=json.dumps(run, ensure_ascii=False, indent=2),
            file_name=f'project_{project_id}_mock_report_{rid}.json', mime='application/json', key=f'download_report_{rid}')


def reports():
    st.header('投资报告')
    project = project_selector(projects_cache, 'report_project')
    if project:
        analysis_panel(project)


def knowledge():
    st.header('知识库')
    st.info('历史 BP 检索、RAG 与投资案例管理将在后续版本上线。当前已上传文件仍保存在本地。')


def settings():
    st.header('系统设置')
    try:
        status = api_request('/api/model/status')
        st.markdown('**模型连接状态**')
        st.write('运行模式：', status.get('mode', '未知'))
        st.write('模型名称：', status.get('model', '未知'))
        if status.get('mode') == 'mock':
            st.info('当前为 Mock 模式，无外部 AI 调用费用。')
        else:
            st.warning('使用真实 API 时，需确认商业资料具有对外发送授权。')
    except Exception as exc:
        st.error('读取模型状态失败：' + error_text(exc))
    st.caption('API Key 请仅保存在后端本地 .env 中，不要粘贴到网页或聊天中。')
    st.divider()
    st.markdown('**开发者工具**')
    st.caption('下面的逐页原文和 Mock 测试仅供开发、排查和证据抽查。')
    if st.toggle('显示开发者调试面板', value=False, key='developer_mode'):
        st.subheader('Mock 智能体测试')
        with st.form('agent_demo'):
            question = st.text_area('测试问题', value='请说明投资分析中为什么要区分项目吸引力与证据完备度？', max_chars=3000)
            ask = st.form_submit_button('执行测试')
        if ask:
            try:
                result = api_request('/api/agents/demo', 'POST', {'question': question})
                st.write(result.get('answer', ''))
                st.caption(f"模型：{result.get('model', '未知')} · 耗时：{result.get('elapsed_ms', '-')} ms")
            except Exception as exc:
                st.error('测试失败：' + error_text(exc))
        st.divider()
        st.subheader('查看文档解析原文')
        project = project_selector(projects_cache, 'debug_project')
        if project:
            try:
                docs = list_docs(project['id'])
                if docs:
                    lookup = {d['id']: d for d in docs}
                    selected = st.selectbox('选择文件', list(lookup),
                                            format_func=lambda i: f"#{i} · {lookup[i]['filename']}", key='debug_document')
                    current = lookup[selected]
                    if current['segments']:
                        total_pages = max(1, (current['segments'] + 29) // 30)
                        page = st.number_input('片段批次（每批最多 30 条）', min_value=1, max_value=total_pages, value=1)
                        result = api_request(f'/api/documents/{selected}/segments?offset={(page-1)*30}&limit=30')
                        for part in result['items']:
                            with st.expander(part['location']):
                                st.text(part['content'])
                    else:
                        st.info('此文件没有可查看的原文片段。')
                else:
                    st.info('项目还没有文件。')
            except Exception as exc:
                st.error('读取原文失败：' + error_text(exc))


st.sidebar.title('VC Intelligence')
st.sidebar.caption('投资决策平台 · 本地开发版')
page = st.sidebar.radio('功能导航', ['项目总览', '项目工作台', '投资报告', '知识库', '系统设置'], key='nav_page')
st.sidebar.divider()
st.sidebar.caption('本地开发版 · 模拟分析流程')
st.title('VC Intelligence Platform')
try:
    health = api_request('/health')
    if health.get('status') != 'ok':
        st.warning('后端状态异常')
except Exception as exc:
    st.error('无法连接后端。请从 start_platform.bat 一键启动，并确认后端服务运行正常。')
    st.caption(error_text(exc))
    st.stop()
try:
    projects_cache = api_request('/api/projects')
except Exception as exc:
    st.error('无法读取项目：' + error_text(exc))
    st.stop()

if page == '项目总览':
    dashboard(projects_cache)
elif page == '项目工作台':
    workspace(projects_cache)
elif page == '投资报告':
    reports()
elif page == '知识库':
    knowledge()
else:
    settings()
