// script.js – simple IntersectionObserver to trigger fade‑in effects

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
});

document.querySelectorAll('.fade').forEach((el) => observer.observe(el));
