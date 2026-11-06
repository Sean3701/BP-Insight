"""Versioned VC field catalog. Future LLM adapters use the same keys."""
CATEGORIES = {
 'basic': '项目概况', 'financing':'融资与估值','team':'团队与治理',
 'technology':'技术与产品','market':'市场与竞争','business':'商业化与财务',
 'risk':'风险与尽调'
}
# key, title, category, priority, expected type
SPEC = [
 ('company_name','企业名称','basic',1,'text'), ('industry','所属行业','basic',2,'text'),
 ('established_year','成立年份','basic',3,'year'), ('location','企业所在地','basic',4,'text'),
 ('financing_round','融资轮次','financing',1,'text'),('financing_amount','本轮计划融资','financing',2,'money'),
 ('valuation','投前/投后估值','financing',3,'money'),('use_of_funds','资金用途','financing',4,'text'),
 ('past_financing','历史融资','financing',5,'text'),
 ('founders','创始人及背景','team',1,'text'),('team','核心团队','team',2,'text'),
 ('equity','股权结构','team',3,'text'),('headcount','员工规模','team',4,'number'),
 ('product','核心产品','technology',1,'text'),('technology','核心技术','technology',2,'text'),
 ('tech_moat','技术壁垒','technology',3,'text'),('patents','知识产权','technology',4,'text'),
 ('rd_stage','研发/量产阶段','technology',5,'text'),
 ('target_market','目标市场','market',1,'text'),('market_size','市场规模','market',2,'money'),
 ('competition','竞争格局','market',3,'text'),
 ('business_model','商业模式','business',1,'text'),('customers','客户与订单','business',2,'text'),
 ('revenue','营业收入','business',3,'money'),('gross_margin','毛利率','business',4,'percentage'),
 ('cash_flow','现金流','business',5,'money'), ('growth_rate','增长率','business',6,'percentage'),
 ('risks','主要风险','risk',1,'text'), ('due_diligence','待核实事项','risk',2,'text'),
]
FIELD_CATALOG=[dict(key=k,label=label,category=cat,priority=prio,data_type=typ) for k,label,cat,prio,typ in SPEC]
FIELD_BY_KEY={f['key']:f for f in FIELD_CATALOG}
FIELD_LABELS={f['key']:f['label'] for f in FIELD_CATALOG}
