import { createClient } from 'genlayer-js';
import { parseEventLogs } from 'viem';
import { testnetBradbury } from 'genlayer-js/chains';
import demo from '../calibration/demo-brief.json';

const CONTRACT = '0xe53c01FF26a6787Af29499668e80502195A3447B';
const EXPLORER = 'https://explorer-bradbury.genlayer.com';
const STORAGE = `retainer:${CONTRACT}:transactions:v1`;
const reader = createClient({chain:testnetBradbury});
const $ = (id) => document.getElementById(id);
const json = (value) => JSON.stringify(value, (_, v) => typeof v === 'bigint' ? v.toString() : v, 2);
const equal = (a,b) => !!a && !!b && a.toLowerCase() === b.toLowerCase();
let account = null, writer = null, selected = null, overview = null, credit = 0n, busy = false;
let activeSubmission = null, briefLoadVersion = 0;
let journal = [], polling = false, pollingUntil = Date.now() + 30*60*1000;
try {journal = JSON.parse(localStorage.getItem(STORAGE) || '[]').filter(t => /^0x[0-9a-f]{64}$/i.test(t.hash)).slice(-100);} catch { /* Storage is optional; writes check it before signing. */ }
const read = (functionName,args=[]) => reader.readContract({address:CONTRACT,functionName,args,jsonSafeReturn:true});
function notify(message){$('notice').textContent=message;}
function save(){localStorage.setItem(STORAGE,json(journal));}
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(className)node.className=className;return node;}
function textInto(id,value){$(id).textContent=value;}
function preset(){for(const [id,value] of Object.entries({'brief-title':demo.title,'brief-spec':demo.spec,probes:json(demo.probes),fee:demo.fee,stake:demo.stake_required,horizon:demo.horizon}))$(id).value=value;}
function updateControls(){
 $('open-button').disabled=!account||busy;
 $('brief-select').disabled=busy;
 $('withdraw').disabled=!account||busy||credit<=0n;
 $('connect').disabled=busy;
 $('connect').textContent=account?'Change / reconnect wallet':'Connect wallet';
 renderBrief();
}
function renderBrief(){
 const target=$('brief-detail');target.replaceChildren();$('brief-actions').replaceChildren();
 $('delivery-form').hidden=true;
 if(!selected){target.append(element('p','No on-chain brief selected.'));return;}
 const b=selected;
 target.append(element('h3',b.title));
 const dl=element('dl');
 for(const [label,value] of [['State',b.status],['Gate',b.gate],['Verdict',b.verdict||'Not judged'],['Requester',b.requester],['Agent',b.agent],['Recorded fee',`${b.fee} wei`],['Stake required',`${b.stake_required} wei`],['Stake locked',`${b.stake_locked} wei`],['Judge output',b.judge_raw||'Not run'],['Defence A / B',`${b.defence_a} / ${b.defence_b}`]]){dl.append(element('dt',label),element('dd',value));}
 if(b.status==='REJECTED')target.append(element('p','The gate rejected this brief. Its recorded fee was credited to the requester; it is not held in escrow.'));
 target.append(dl,element('h3','Pinned acceptance specification'),element('p',b.spec,'body-text'));
 if(b.delivery){target.append(element('h3','Stored delivery'),element('p',b.delivery.body||'No body stored.','body-text'));}
 if(b.deliveryError)target.append(element('p',`Delivery read failed: ${b.deliveryError}`));
 textInto('raw-record',json(b));
 function action(label,method,value=0n){const button=element('button',label);button.type='button';button.disabled=busy||!account;button.onclick=()=>send(method,[Number(b.brief_id)],value);$('brief-actions').append(button);}
 if(b.status==='OPEN'){
  if(equal(account,b.requester))action('Cancel & credit fee','cancel_brief');
  else action(`Accept & stake ${b.stake_required} wei`,'accept',BigInt(b.stake_required));
 }
 if(['ACCEPTED','DELIVERED'].includes(b.status)&&equal(account,b.agent))$('delivery-form').hidden=false;
 if(b.status==='DELIVERED')action('Judge & settle','judge');
 if(b.status==='ACCEPTED'&&(equal(account,b.agent)||equal(account,b.requester))&&Number(overview?.seq)-Number(b.accepted_at)>Number(b.horizon))action('Expire overdue brief','expire');
 $('delivery-form').querySelector('button[type=submit]').disabled=busy||!account;
}
async function loadBrief(){
 const id=$('brief-select').value, version=++briefLoadVersion;
 selected=null;renderBrief();
 if(id==='')return;
 $('brief-detail').replaceChildren(element('p',`Reading brief #${id}…`));
 const brief=await read('get_brief',[Number(id)]);
 try{brief.delivery=await read('get_delivery',[Number(id)]);}catch(error){brief.deliveryError=error.message||String(error);}
 if(version!==briefLoadVersion||$('brief-select').value!==id)return;
 selected=brief;renderBrief();
}
async function refresh(quiet=false){
 if(!quiet)notify('Reading contract state from Bradbury…');
 try{
 const [state,count]=await Promise.all([read('get_overview'),read('brief_count')]);overview=state;
 $('overview').replaceChildren();
 for(const [label,value] of [['Briefs recorded',count],['Settled',state.settled],['Rejected by gate',state.rejected_by_gate],['Escrowed · wei',state.escrowed]]){const node=element('div',undefined,'metric');node.append(element('strong',value),element('span',label));$('overview').append(node);}
 const previous=$('brief-select').value;
 $('brief-select').replaceChildren();
 for(let i=Number(count)-1;i>=Math.max(0,Number(count)-50);i--){const option=element('option',`Brief #${i}`);option.value=String(i);$('brief-select').append(option);}
 if(!Number(count)){const option=element('option','No briefs stored on chain');option.value='';$('brief-select').append(option);}
 if(previous!==''&&Number(previous)<Number(count)&&Number(previous)>=Math.max(0,Number(count)-50))$('brief-select').value=previous;
 await loadBrief();
 if(account){credit=BigInt(await read('balance_of',[account]));textInto('credit',`${credit} wei available to withdraw`);}else{credit=0n;}
 textInto('updated',`Read at ${new Date().toLocaleTimeString()}`);updateControls();
 if(!quiet)notify(`Live state loaded. ${Number(count)>50?'Showing the latest 50 briefs. ':''}${account?'Wallet connected.':'No wallet needed to inspect the ledger.'}`);
 }catch(error){textInto('updated','RPC read failed');notify(`Could not refresh Bradbury: ${error.shortMessage||error.message||String(error)}. Displayed records may be stale; retry Refresh chain.`);}
}
async function connect(){
 try{
 if(!window.ethereum)throw new Error('No browser wallet found. Open this page in a wallet browser or install an EIP-1193 wallet.');
 const provider=window.ethereum;
 const accounts=await provider.request({method:'eth_requestAccounts'});
 const chainId=`0x${testnetBradbury.id.toString(16)}`;
 try{await provider.request({method:'wallet_switchEthereumChain',params:[{chainId}]});}catch(error){if(Number(error.code)!==4902)throw error;await provider.request({method:'wallet_addEthereumChain',params:[{chainId,chainName:testnetBradbury.name,nativeCurrency:testnetBradbury.nativeCurrency,rpcUrls:[...testnetBradbury.rpcUrls.default.http],blockExplorerUrls:[EXPLORER]}]});await provider.request({method:'wallet_switchEthereumChain',params:[{chainId}]});}
 if(Number(await provider.request({method:'eth_chainId'}))!==4221)throw new Error('Select Bradbury chain 4221 to continue.');
 if(!accounts[0])throw new Error('Wallet returned no account.');
 account=accounts[0];
 const trackedProvider={request:async(request)=>{
   // Consensus submissions can outgrow the SDK's exact gas estimate before mining.
   // Keep a 50% headroom; the wallet shows the limit and only used gas is charged.
   if(request.method==='eth_sendTransaction'&&request.params?.[0]?.gas){
     const tx=request.params[0];
     request={...request,params:[{...tx,gas:`0x${((BigInt(tx.gas)*3n+1n)/2n).toString(16)}`},...request.params.slice(1)]};
   }
   const result=await provider.request(request);
   if(request.method==='eth_sendTransaction'&&activeSubmission){
     activeSubmission.evmHash=result;activeSubmission.hash=result;activeSubmission.status='EVM_PENDING';
     journal.push(activeSubmission);
     try{save();}catch{notify(`Submitted EVM transaction ${result}. Storage failed; copy this hash before closing.`);}
     renderHistory();
   }
   return result;
 }};
 writer=createClient({chain:testnetBradbury,account,provider:trackedProvider});
 textInto('wallet-name','Bradbury wallet connected');textInto('wallet-detail',account);await refresh();
 }catch(error){notify(`Wallet connection: ${error.shortMessage||error.message||String(error)}`);}
}
function terminal(t){return ['FINALIZED','UNDETERMINED','CANCELED','EVM_REVERTED'].includes(t.status);}
function renderHistory(){
 $('history').replaceChildren();
 if(!journal.length){$('history').append(element('p','No transactions submitted from this browser.'));return;}
 for(const item of [...journal].reverse()){
 const node=element('article',undefined,'journal-entry');
 node.append(element('h3',`${item.method} · ${item.status||'SUBMITTED'}`));
 const link=element('a',item.hash);link.href=`${EXPLORER}/transactions/${item.hash}`;link.target='_blank';link.rel='noopener';node.append(link);
 let note='Waiting for consensus. Your transaction remains on chain if you close this page.';
 if(item.status==='ACCEPTED'||item.status==='READY_TO_FINALIZE')note='Provisional consensus decision. It can still change before finalization.';
 if(item.status==='FINALIZED')note=item.execution==='FINISHED_WITH_RETURN'?'Finalized with successful contract execution. Inspect the refreshed ledger for the resulting state.':'Finalized, but successful execution is not confirmed. Inspect the execution result.';
 if(item.execution==='FINISHED_WITH_ERROR')note='Contract execution failed. Consensus status alone does not mean the action succeeded.';
 if(item.status==='UNDETERMINED')note='Consensus was not reached. No successful state change is claimed; inspect the ledger before retrying.';
 if(item.status==='EVM_PENDING')note='Wallet transaction broadcast; waiting for the GenLayer consensus transaction ID. This EVM hash is saved for recovery.';
 if(item.status==='EVM_REVERTED')note='EVM transaction reverted. The contract action was not accepted for consensus.';
 if(item.status==='CANCELED')note='Transaction canceled. No successful state change is claimed.';
 node.append(element('p',note),element('p',`Execution: ${item.execution||'Not available yet'} · ${new Date(item.created).toLocaleString()}`));
 if(item.error)node.append(element('p',`Status check: ${item.error}`));
 if(!terminal(item)&&Date.now()>pollingUntil)node.append(element('p','Polling paused. Use Resume status checks to continue.'));
 if(item.receipt){const detail=element('details');detail.append(element('summary','Consensus receipt'),element('pre',json(item.receipt)));node.append(detail);}
 $('history').append(node);
 }
}
async function poll(){
 if(polling||Date.now()>pollingUntil){renderHistory();return;}
 polling=true;let changed=false;
 try{
 for(const item of journal.filter(t=>!terminal(t))){
 try{
 if(item.status==='EVM_PENDING'){
   const evmReceipt=await reader.getTransactionReceipt({hash:item.evmHash});
   if(evmReceipt.status==='reverted'){item.status='EVM_REVERTED';item.receipt=evmReceipt;changed=true;continue;}
   const events=parseEventLogs({abi:testnetBradbury.consensusMainContract.abi,eventName:'NewTransaction',logs:evmReceipt.logs});
   const txId=events[0]?.args?.txId;
   if(!txId)throw new Error('EVM receipt has no NewTransaction event yet. Inspect the wallet transaction before resubmitting.');
   item.hash=txId;item.status='SUBMITTED';
 }
 const receipt=await reader.getTransaction({hash:item.hash});const prior=item.status;item.status=receipt.statusName||(typeof receipt.status==='string'?receipt.status:'PENDING');item.execution=receipt.txExecutionResultName||({0:'NOT_VOTED',1:'FINISHED_WITH_RETURN',2:'FINISHED_WITH_ERROR'}[receipt.txExecutionResult]);item.receipt=receipt;delete item.error;changed ||= prior!==item.status;}
 catch(error){item.error=error.shortMessage||error.message||String(error);}
 }
 try{save();}catch(error){notify(`Journal storage failed. Keep the transaction hash: ${error.message}`);}
 renderHistory();if(changed)await refresh(true);
 }finally{polling=false;}
}
async function send(method,args=[],value=0n){
 if(busy)return;
 if(!account||!writer){notify('Connect your wallet on Bradbury first.');return;}
 busy=true;updateControls();
 try{
 // Require writable storage before opening a wallet request. Never silently lose a hash.
 save();
 notify(`Confirm ${method} in your wallet. Value: ${value} wei, plus network fees.`);
 activeSubmission={method,args:JSON.parse(json(args)),value:String(value),account,created:new Date().toISOString(),status:'AWAITING_WALLET'};
 const hash=await writer.writeContract({address:CONTRACT,functionName:method,args,value});
 if(!/^0x[0-9a-f]{64}$/i.test(hash))throw new Error('Wallet returned an unexpected transaction hash. Check wallet activity before retrying.');
 if(activeSubmission.evmHash){activeSubmission.hash=hash;activeSubmission.status='SUBMITTED';}else{journal.push({...activeSubmission,hash,status:'SUBMITTED'});}
 try{save();}catch(error){notify(`Transaction submitted: ${hash}. Browser storage failed; copy this hash before closing.`);}
 pollingUntil=Date.now()+30*60*1000;renderHistory();notify(`Submitted ${method}: ${hash}. Following consensus and execution in the journal.`);await poll();
 }catch(error){notify(`${method}: ${error.shortMessage||error.message||String(error)}. No automatic retry was sent.`);}
 finally{activeSubmission=null;busy=false;updateControls();}
}
$('contract-link').textContent=CONTRACT;$('contract-link').href=`${EXPLORER}/contracts/${CONTRACT}`;
$('connect').onclick=connect;$('refresh').onclick=()=>refresh();$('preset').onclick=preset;
$('brief-select').onchange=()=>loadBrief().catch(error=>notify(`Brief read failed: ${error.message}`));
$('withdraw').onclick=()=>send('withdraw');
$('resume').onclick=()=>{pollingUntil=Date.now()+30*60*1000;poll();};
$('sample-body').onclick=()=>{$('delivery-body').value=demo.probes[0];};
$('delivery-form').onsubmit=(event)=>{event.preventDefault();if(!selected)return;const body=$('delivery-body').value;if(!body.trim()||new TextEncoder().encode(body).length>8192){notify('Delivery must contain 1–8192 UTF-8 bytes.');return;}send('deliver',[Number(selected.brief_id),JSON.stringify({version:'retainer/1',brief_id:Number(selected.brief_id),body})]);};
$('open-form').onsubmit=async(event)=>{event.preventDefault();try{
 const spec=$('brief-spec').value,probes=JSON.parse($('probes').value),fee=BigInt($('fee').value),stake=BigInt($('stake').value),horizon=Number($('horizon').value);
 if(!spec.trim()||[...spec].length>8192||fee<=0n||stake<=0n||!Number.isInteger(horizon)||horizon<1||horizon>1000)throw new Error('Enter a spec, positive integer amounts, and a horizon from 1 to 1000.');
 if(!Array.isArray(probes)||!probes.length||probes.length>8||probes.some(p=>typeof p!=='string'||!p.trim()||[...p].length>8192))throw new Error('Use 1–8 nonempty probe strings, each at most 8192 characters.');
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(spec));
 const fingerprint=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
 await send('open_brief',[$('brief-title').value,spec,fingerprint,JSON.stringify(probes),stake,horizon],fee);
 }catch(error){notify(`Check new brief: ${error.message}`);}};
function disconnect(){account=null;writer=null;credit=0n;textInto('wallet-name','Read-only visitor');textInto('wallet-detail','Account or network changed. Reconnect to confirm the selected Bradbury wallet.');textInto('credit','Connect wallet to read your balance.');updateControls();}
window.ethereum?.on?.('accountsChanged',disconnect);window.ethereum?.on?.('chainChanged',disconnect);
preset();renderHistory();refresh();poll();setInterval(poll,12000);
