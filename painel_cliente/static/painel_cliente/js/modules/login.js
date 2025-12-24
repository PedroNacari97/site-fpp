export const initLoginFocus = () => {
  const loginPage = document.querySelector(".login-page");
  if (!loginPage) {
    return;
  }

  const firstInput = document.querySelector(
    "input[type='text'], input[type='email'], input[type='password']"
  );
  if (firstInput) {
    firstInput.focus();
  }
};
