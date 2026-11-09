"""Browser QA server: disposable storage and explicit fake external transport only."""
import os,sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['VC_DATA_DIR']=str(Path(__file__).resolve().parents[1]/'data'/'browser-qa')
from backend import providers

def fixture_generate(config,messages):
    if messages[0]['role']=='user':
        return {'text':'OK','usage':{'total_tokens':2}}
    context=json.loads(messages[-1]['content'])
    sid=context['sources'][0]['id']
    result=({'answer':'测试回答：产品来自企业资料，尚未核验。','source_ids':[sid]} if context['question'] else
            {'summary':'浏览器验收报告：企业研发工业机器人，以下为测试替身输出。',
             'sections':[{'title':'项目概况','body':'企业资料披露其核心产品为工业机器人。需要核验订单和客户信息。','source_ids':[sid]},
                         {'title':'风险与尽调','body':'应补充客户合同、研发投入及现金流资料。','source_ids':[]}],
             'questions':['请提供最近一期客户订单与回款依据。']})
    return {'text':json.dumps(result,ensure_ascii=False),'usage':{'total_tokens':120}}
providers.generate=fixture_generate
from backend.main import app
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8504)
