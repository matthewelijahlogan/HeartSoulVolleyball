/* js/script.js */
function toggleMenu() {
  const menu = document.getElementById('dropdownMenu');
  menu.classList.toggle('show');

  // Animate each link with a staggered delay
  if (menu.classList.contains('show')) {
    const links = menu.querySelectorAll('a');
    links.forEach((link, index) => {
      link.style.setProperty('--i', index);
    });
  }
}
