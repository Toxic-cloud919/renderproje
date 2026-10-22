const authView=document.querySelector('#authView'),chatView=document.querySelector('#chatView'),form=document.querySelector('#authForm'),notice=document.querySelector('#notice');
const emailInput=document.querySelector('#email'),passwordInput=document.querySelector('#password'),codeInput=document.querySelector('#code'),nameInput=document.querySelector('#name');
let mode='login',me=null,activeFriend=null,pollTimer=null,lastMessageId=0;

function setMode(next){
  mode=next;notice.textContent='';notice.style.color='';
  const registering=mode==='register',forgot=mode==='forgotEmail'||mode==='forgotReset';
  const verifying=mode==='registerVerify'||mode==='forgotReset';
  document.querySelector('#loginTab').classList.toggle('active',mode==='login');
  document.querySelector('#registerTab').classList.toggle('active',registering||mode==='registerVerify');
  document.querySelector('#loginTab').setAttribute('aria-selected',String(mode==='login'));
  document.querySelector('#registerTab').setAttribute('aria-selected',String(registering||mode==='registerVerify'));
  document.querySelector('#authTabs').classList.toggle('hidden',forgot||mode==='registerVerify');
  const titles={login:['Tekrar hoş geldin','Devam etmek için e-posta adresini gir.'],register:['Hesabını oluştur','E-postana doğrulama kodu göndereceğiz.'],registerVerify:['E-postanı doğrula','E-postana gelen 6 haneli kodu yaz.'],forgotEmail:['Şifreni yenile','Kayıtlı e-postana yenileme kodu göndereceğiz.'],forgotReset:['Yeni şifre belirle','E-postana gelen kodu ve yeni şifreni yaz.']};
  document.querySelector('#heading').textContent=titles[mode][0];
  document.querySelector('#subheading').textContent=titles[mode][1];
  document.querySelector('#nameGroup').classList.toggle('hidden',!registering);
  nameInput.required=registering;
  document.querySelector('#codeGroup').classList.toggle('hidden',!verifying);
  document.querySelector('#resendRow').classList.toggle('hidden',!verifying);
  codeInput.required=verifying;
  document.querySelector('#passwordGroup').classList.toggle('hidden',mode==='forgotEmail'||mode==='registerVerify');
  passwordInput.required=mode==='login'||registering||mode==='forgotReset';
  passwordInput.autocomplete=registering||mode==='forgotReset'?'new-password':'current-password';
  document.querySelector('#passwordLabel').textContent=mode==='forgotReset'?'Yeni şifre':'Şifre';
  emailInput.readOnly=verifying;
  document.querySelector('#rememberRow').classList.toggle('hidden',!(mode==='login'||forgot));
  document.querySelector('#forgot').textContent=mode==='login'?'Şifremi unuttum':'Girişe dön';
  document.querySelector('#submitText').textContent=mode==='login'?'Giriş yap':registering||mode==='forgotEmail'?'Kod gönder':mode==='registerVerify'?'Kodu doğrula':'Şifreyi değiştir';
}

async function api(url,opts={}){
  const res=await fetch(url,{credentials:'same-origin',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});
  const data=await res.json();if(!res.ok)throw Error(data.error||'İşlem başarısız.');return data;
}
function signedIn(user){me=user;authView.classList.add('hidden');chatView.classList.remove('hidden');document.querySelector('#accountLabel').textContent=user.name+' · '+user.email;refreshFriends()}
function showError(el,msg){el.textContent=msg;el.classList.add('error')}
function showOk(el,msg){el.textContent=msg;el.classList.remove('error')}

document.querySelector('#loginTab').onclick=()=>setMode('login');
document.querySelector('#registerTab').onclick=()=>setMode('register');
document.querySelector('#showPass').onclick=e=>{passwordInput.type=passwordInput.type==='password'?'text':'password';e.currentTarget.textContent=passwordInput.type==='password'?'Göster':'Gizle'};
document.querySelector('#resendCode').onclick=async()=>{
  notice.style.color='';notice.textContent='Yeni kod isteniyor…';
  try{
    const result=mode==='registerVerify'
      ?await api('/api/register',{method:'POST',body:JSON.stringify({email:emailInput.value.trim(),password:passwordInput.value,name:nameInput.value.trim()})})
      :await api('/api/forgot-password',{method:'POST',body:JSON.stringify({email:emailInput.value.trim()})});
    notice.textContent=result.message;
  }catch(err){notice.textContent=err.message}
};
document.querySelector('#forgot').onclick=e=>{e.preventDefault();if(mode==='login')setMode('forgotEmail');else{setMode('login');passwordInput.value='';codeInput.value='';emailInput.readOnly=false}};
form.onsubmit=async e=>{
  e.preventDefault();notice.style.color='';notice.textContent='İşleniyor…';
  const email=emailInput.value.trim(),password=passwordInput.value,code=codeInput.value.trim(),name=nameInput.value.trim();
  try{
    let result;
    if(mode==='login'){result=await api('/api/login',{method:'POST',body:JSON.stringify({email,password})});signedIn(result.user);return}
    if(mode==='register'){result=await api('/api/register',{method:'POST',body:JSON.stringify({email,password,name})});setMode('registerVerify');notice.textContent=result.message;return}
    if(mode==='registerVerify'){result=await api('/api/verify-registration',{method:'POST',body:JSON.stringify({email,code})});signedIn(result.user);return}
    if(mode==='forgotEmail'){result=await api('/api/forgot-password',{method:'POST',body:JSON.stringify({email})});setMode('forgotReset');notice.textContent=result.message;return}
    if(mode==='forgotReset'){result=await api('/api/reset-password',{method:'POST',body:JSON.stringify({email,code,password})});setMode('login');emailInput.value=email;emailInput.readOnly=false;passwordInput.value='';codeInput.value='';notice.textContent=result.message;notice.style.color='#37845f'}
  }catch(err){notice.textContent=err.message}
};
document.querySelector('#logoutButton').onclick=async()=>{try{await api('/api/logout',{method:'POST',body:'{}'})}finally{clearInterval(pollTimer);me=null;activeFriend=null;chatView.classList.add('hidden');authView.classList.remove('hidden');setMode('login')}};
document.querySelector('#friendForm').onsubmit=async e=>{e.preventDefault();const el=document.querySelector('#friendNotice');try{const result=await api('/api/friend-requests',{method:'POST',body:JSON.stringify({email:document.querySelector('#friendEmail').value.trim()})});showOk(el,result.message);document.querySelector('#friendEmail').value='';refreshFriends()}catch(err){showError(el,err.message)}};

async function refreshFriends(){
  try{
    const data=await api('/api/friends'),list=document.querySelector('#friendsList');list.replaceChildren();
    if(!data.friends.length)list.innerHTML='<div class="empty-small">Henüz arkadaşın yok.</div>';
    for(const f of data.friends){
      const b=document.createElement('button');b.className='friend-item'+(activeFriend?.id===f.id?' selected':'');
      const avatar=document.createElement('span');avatar.className='avatar mini';avatar.textContent=(f.name||'?').slice(0,1).toUpperCase();
      const info=document.createElement('span');info.className='friend-info';const n=document.createElement('strong');n.textContent=f.name;const mail=document.createElement('small');mail.textContent=f.email;info.append(n,mail);b.append(avatar,info);b.onclick=()=>selectFriend(f);list.append(b);
    }
    const wrap=document.querySelector('#incomingWrap'),incoming=document.querySelector('#incomingList');incoming.replaceChildren();wrap.classList.toggle('hidden',!data.incoming.length);
    for(const req of data.incoming){
      const row=document.createElement('div');row.className='request-row';const text=document.createElement('span');text.textContent=req.name+' ('+req.email+')';
      const btn=document.createElement('button');btn.textContent='Kabul';btn.onclick=async()=>{try{await api('/api/friend-requests/'+req.id+'/accept',{method:'POST',body:'{}'});refreshFriends()}catch(err){showError(document.querySelector('#friendNotice'),err.message)}};
      row.append(text,btn);incoming.append(row);
    }
  }catch{}
}
function selectFriend(friend){
  activeFriend=friend;lastMessageId=0;document.querySelector('#conversationEmpty').classList.add('hidden');document.querySelector('#conversationActive').classList.remove('hidden');
  document.querySelector('#friendName').textContent=friend.name;document.querySelector('#friendEmailLabel').textContent=friend.email;document.querySelector('#friendAvatar').textContent=friend.name.slice(0,1).toUpperCase();
  document.querySelector('#messages').replaceChildren();refreshFriends();loadMessages();clearInterval(pollTimer);pollTimer=setInterval(loadMessages,2500);
}
async function loadMessages(){
  if(!activeFriend)return;
  try{
    const result=await api('/api/messages?friend='+activeFriend.id),box=document.querySelector('#messages'),nearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<80;
    for(const m of result.messages){
      if(m.id<=lastMessageId)continue;lastMessageId=m.id;
      const bubble=document.createElement('div');bubble.className='bubble '+(m.sender_id===me.id?'mine':'theirs');
      const content=document.createElement('div');content.textContent=m.body;const time=document.createElement('time');time.textContent=new Date(m.created_at*1000).toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'});bubble.append(content,time);box.append(bubble);
    }
    if(nearBottom)box.scrollTop=box.scrollHeight;
  }catch{}
}
document.querySelector('#messageForm').onsubmit=async e=>{
  e.preventDefault();if(!activeFriend)return;const input=document.querySelector('#messageInput'),body=input.value.trim();if(!body)return;input.disabled=true;
  try{await api('/api/messages',{method:'POST',body:JSON.stringify({friend_id:activeFriend.id,body})});input.value='';await loadMessages()}catch(err){alert(err.message)}finally{input.disabled=false;input.focus()}
};
api('/api/me').then(result=>{if(result.user)signedIn(result.user)}).catch(()=>{});
setInterval(()=>{if(me)refreshFriends()},5000);
