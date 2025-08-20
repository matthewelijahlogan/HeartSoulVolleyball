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

// Testimonial Carousel Auto-Rotate
document.addEventListener("DOMContentLoaded", () => {
  const slides = document.querySelectorAll(".carousel-slide");
  let currentSlide = 0;

  function showSlide(index) {
    slides.forEach((slide, i) => {
      slide.classList.toggle("active", i === index);
    });
  }

  function nextSlide() {
    currentSlide = (currentSlide + 1) % slides.length;
    showSlide(currentSlide);
  }

  // Initialize the first slide
  showSlide(currentSlide);

  // Change slide every 10 seconds
  setInterval(nextSlide, 10000);
});
