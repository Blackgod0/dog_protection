const el = id => document.getElementById(id);

let authMsg = el('authMsg');
let profileFormSection = el('profileForm');
let recommendationsSection = el('recommendations');

// --- Generic API helper with session cookies enabled ---
async function api(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include'   // 🔑 ensures cookies (Flask session) are sent
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch('/api' + path, opts);
  return res.json();
}

// --- Auth ---
el('btnRegister').addEventListener('click', async () => {
  const username = el('username').value.trim();
  const password = el('password').value;
  if (!username || !password) {
    authMsg.innerText = "Please enter username and password";
    return;
  }
  const r = await api('/register', 'POST', { username, password });
  authMsg.innerText = JSON.stringify(r);
});

el('btnLogin').addEventListener('click', async () => {
  const username = el('username').value.trim();
  const password = el('password').value;
  if (!username || !password) {
    authMsg.innerText = "Please enter username and password";
    return;
  }
  const r = await api('/login', 'POST', { username, password });
  authMsg.innerText = JSON.stringify(r);

  if (r.status === 'ok') {
    profileFormSection.style.display = 'block';
    recommendationsSection.style.display = 'block';
    el('btnLogout').style.display = 'inline-block';
  }
});

// --- Logout ---
el('btnLogout').addEventListener('click', async () => {
  const r = await api('/logout', 'POST');
  authMsg.innerText = JSON.stringify(r);

  if (r.status === 'ok') {
    profileFormSection.style.display = 'none';
    recommendationsSection.style.display = 'none';
    el('btnLogout').style.display = 'none';
  }
});

// --- Check if user is already logged in on page load ---
window.addEventListener('DOMContentLoaded', async () => {
  try {
    const r = await api('/profile-check', 'GET');
    if (r.logged_in) {
      profileFormSection.style.display = 'block';
      recommendationsSection.style.display = 'block';
      el('btnLogout').style.display = 'inline-block';
      authMsg.innerText = `Welcome back, ${r.username}`;
    }
  } catch (err) {
    console.log("Not logged in:", err);
  }
});


// --- Dog Profile ---
el('dogForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  const r = await api('/profile', 'POST', payload);
  el('profileMsg').innerText = JSON.stringify(r);
  if (r.dog_id) localStorage.setItem('last_dog_id', r.dog_id);
});

// --- Recommendations ---
el('btnGetRec').addEventListener('click', async () => {
  const dog_id = localStorage.getItem('last_dog_id');
  if (!dog_id) {
    el('recOutput').innerText = "⚠️ No dog profile found. Please create one first.";
    return;
  }

  const r = await api('/recommendations', 'POST', { dog_id, refine_with_gemini: true });

  // Display deterministic info
  let output = `Calories/day: ${r.deterministic.calorie_estimate_kcal_per_day}\n`;
  output += `Category: ${r.deterministic.category}\n`;
  output += `Exercise minutes/day: ${r.deterministic.exercise_minutes_per_day}\n`;
  if (r.deterministic.details.length > 0) {
    output += `Details:\n- ${r.deterministic.details.join("\n- ")}\n`;
  }

  // Append Gemini refinement text directly
  if (r.gemini_refinement) {
    output += `\n--- GEMINI REFINEMENT ---\n${r.gemini_refinement}`;
  }

  el('recOutput').innerText = output;
});
