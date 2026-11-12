const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let completed=false, failed=false, count=0;
 const project={id:991,name:'流程测试 BP'};
 const report=()=>({id:123,project_id:991,project_name:project.name,current_project_name:project.name,kind:'report',model_id:1,model_name:'测试 AI',model:'test',status:completed?'completed':failed?'failed':'running',error:failed?'模拟失败':'',legacy:false,result:{summary:'测试报告',sections:[],questions:[]}});
 await page.route('**/api/**',async route=>{let path=new URL(route.request().url()).pathname;let data=[];
 if(path==='/api/v2/models')data=[{id:1,name:'测试 AI',model:'test',enabled:true,key_configured:true}];
 else if(path==='/api/v2/projects')data=[project];
 else if(path==='/api/v2/projects/991')data=project;
 else if(path.endsWith('/documents'))data=[{filename:'BP.pdf',status:'processed',segments:1,size_bytes:100}];
 else if(path==='/api/v2/reports')data=completed?Array.from({length:count||1},(_,i)=>({...report(),id:123+i})):[];
 else if(path.endsWith('/runs')){if(route.request().method()==='POST'){count++;completed=true;failed=false}data=(completed||failed)?[report()]:[];}
 else if(path==='/api/v2/jobs/123')data=report();
 await route.fulfill({json:data});});
 await page.goto('http://127.0.0.1:8503/app/#create');
 await page.locator('#resumeButton').click();await page.locator('#projectName').waitFor({state:'visible'});
 failed=true;await page.waitForTimeout(3500);if(!await page.locator('#create').isVisible())throw Error('Failure moved draft');
 await page.locator('#runButton').click();await page.waitForURL('**/#library');
 if(!(await page.locator('#reportList').innerText()).includes('流程测试 BP'))throw Error('Missing project');
 if((await page.locator('#resumeProject').innerText()).includes('流程测试 BP'))throw Error('Archived draft retained');
 await page.locator('#runButton').click();await page.waitForTimeout(700);
 if(!(await page.locator('#reportList').innerText()).includes('2 份报告'))throw Error('Not grouped');
 await page.reload();await page.locator('#reportList [data-project]').click();await page.locator('[data-job]').first().click();await page.getByRole('link',{name:'下载报告 PDF'}).waitFor();
 await page.getByRole('button',{name:'创建分析',exact:true}).click();await page.locator('#uploadCard').waitFor({state:'visible'});
 if(await page.locator('#projectCard').isVisible())throw Error('Create not cleared');
 if(errors.length)throw Error(errors.join(';'));await browser.close();console.log('PASS: failure retains draft, first completion archives, additional reports group, reload, PDF entry, create resets');
})().catch(e=>{console.error(e);process.exit(1)});
