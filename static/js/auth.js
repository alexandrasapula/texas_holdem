document.addEventListener("DOMContentLoaded", () => {
    const btnLogin = document.getElementById("btn-login");
    const btnSignup = document.getElementById("btn-signup");
    const panelLogin = document.getElementById("panel-login");
    const panelSignup = document.getElementById("panel-signup");
    const glider = document.getElementById("glider");
   
    function showTab(tab) {
      const isLogin = tab === "login";
      btnLogin.classList.toggle("active", isLogin);
      btnSignup.classList.toggle("active", !isLogin);
      panelLogin.classList.toggle("active", isLogin);
      panelSignup.classList.toggle("active", !isLogin);
      glider.style.transform = isLogin ? "translateX(0)" : "translateX(100%)";
    }
   
    btnLogin.addEventListener("click", () => showTab("login"));
    btnSignup.addEventListener("click", () => showTab("signup"));
    document.getElementById("link-signup").addEventListener("click", () => showTab("signup"));
    document.getElementById("link-login").addEventListener("click", () => showTab("login"));
   
    showTab(document.body.dataset.activeTab || "login");
});
