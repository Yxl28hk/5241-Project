function renderAccountSecurity() {
  const user = state.user;
  const pending = user?.verification_required && !user?.email_verified;
  $('#account-status').classList.toggle('hidden', !pending);
  $('#account-status').textContent = pending ? '请先验证邮箱，再使用学习与教学功能。点击右上角头像可发送验证邮件。' : '';
  const labels = {pending:'教师申请待审核（请先验证邮箱并填写教学用途）', approved:'教师身份已通过审核', rejected:'教师申请未通过，可补充教学用途后重新提交', none:'学生账号'};
  $('#account-verification-status').textContent = user ? (user.email_verified ? '邮箱已验证。' : '邮箱尚未验证。') + (user.role === 'admin' ? '管理员账号' : labels[user.teacher_status] || '') : '';
  $('#send-verification').disabled = !user || user.email_verified;
  $('#teacher-application-form').classList.toggle('hidden', !user || user.role !== 'student');
}
async function accountAction(button, feedback, operation) {
  if (button.disabled) return;
  button.disabled = true; $(feedback).textContent = '正在处理…';
  try { const result = await operation(); $(feedback).textContent = result.message; return result; }
  catch (error) { $(feedback).textContent = error.message; }
  finally { button.disabled = false; }
}
$('#send-verification').onclick = event => accountAction(event.currentTarget, '#verification-feedback', () => zhixingApi.requestVerification());
$('#teacher-application-form').onsubmit = async event => {
  event.preventDefault();
  const result = await accountAction(event.target.querySelector('button'), '#teacher-application-feedback', () => zhixingApi.applyTeacher({reason:$('#teacher-application-reason').value.trim()}));
  if (result && state.user) { state.user.teacher_status='pending'; renderAccountSecurity(); }
};
function openAccountAction(mode, token='') {
  const reset = mode === 'reset', verify = mode === 'verify';
  $('#account-action-title').textContent = verify ? '验证邮箱' : reset ? '设置新密码' : '找回密码';
  $('#account-action-feedback').textContent = '';
  $('#account-action-content').innerHTML = `<p>${verify ? '点击确认完成邮箱验证。' : reset ? '设置新密码后，所有旧登录会话将失效。' : '输入注册邮箱，我们会发送密码重置链接。'}</p><form id="account-action-form">${verify ? '' : reset ? '<label class="field">新密码<input id="recovery-password" type="password" autocomplete="new-password" minlength="6" maxlength="128" required></label><label class="field">确认新密码<input id="recovery-confirm" type="password" autocomplete="new-password" minlength="6" maxlength="128" required></label>' : '<label class="field">注册邮箱<input id="recovery-email" type="email" autocomplete="email" maxlength="254" required></label>'}<button class="button button-primary" type="submit">${verify ? '确认验证' : reset ? '重置密码' : '发送重置链接'}</button></form>`;
  $('#account-action-form').onsubmit = async event => {
    event.preventDefault();
    if (reset && $('#recovery-password').value !== $('#recovery-confirm').value) { $('#account-action-feedback').textContent='两次密码不一致'; return; }
    const button=event.target.querySelector('button');
    const result=await accountAction(button, '#account-action-feedback', () => verify ? zhixingApi.confirmVerification({token}) : reset ? zhixingApi.resetPassword({token,password:$('#recovery-password').value}) : zhixingApi.requestPasswordReset({email:$('#recovery-email').value.trim()}));
    if (result && (verify || reset)) {
      button.disabled=true;
      if (reset) { state.user=null; updateUserUI(); }
      else if (state.user) { const me=await zhixingApi.getCurrentUser(); state.user=me.user; updateUserUI(); }
      const back=document.createElement('button');back.type='button';back.className='button button-ghost';back.textContent='返回登录';
      back.onclick=()=>{switchAuth('login');openModal('#auth-modal');};event.target.append(back);
    }
  };
  openModal('#account-action-modal');
}
$('#forgot-password').onclick = () => openAccountAction('request');
$('#load-teacher-applications').onclick = async event => {
  const button=event.currentTarget;button.disabled=true;
  const container=$('#teacher-applications');container.textContent='正在加载…';
  try {
    const result=await zhixingApi.teacherApplications();container.textContent='';
    if (!result.applications.length) container.textContent='暂无待审核申请。';
    for (const applicant of result.applications) {
      const card=document.createElement('section');card.className='account-security-panel';
      card.innerHTML=`<h3>${escapeHTML(applicant.name)}</h3><p>${escapeHTML(applicant.email)} · ${applicant.email_verified_at?'邮箱已验证':'邮箱未验证'}</p><p>${escapeHTML(applicant.teacher_reason || '尚未填写教学用途')}</p><label class="field">审核说明<textarea maxlength="1000" required></textarea></label><button type="button" class="button button-primary" data-decision="approve">通过</button> <button type="button" class="button button-ghost" data-decision="reject">退回补充</button><p role="status"></p>`;
      card.querySelectorAll('[data-decision]').forEach(action=>{action.onclick=async()=>{
        const reason=card.querySelector('textarea').value.trim();const feedback=card.querySelector('[role="status"]');
        if (!reason) {feedback.textContent='请填写审核说明';return;}
        card.querySelectorAll('button').forEach(item=>item.disabled=true);
        try {const reply=await zhixingApi.reviewTeacher(applicant.id,{decision:action.dataset.decision,reason});feedback.textContent=reply.message;}
        catch(error){feedback.textContent=error.message;card.querySelectorAll('button').forEach(item=>item.disabled=false);}
      };});
      container.append(card);
    }
  } catch(error){container.textContent=error.message;}
  finally{button.disabled=false;}
};
// Do not consume emailed links on GET: mail scanners must not use a token.
const accountLink = location.hash.match(/^#account-(verify|reset)=([A-Za-z0-9_-]{20,200})$/);
if (accountLink) {history.replaceState(null,'',location.pathname+location.search);openAccountAction(accountLink[1],accountLink[2]);}
