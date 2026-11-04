(function () {
  "use strict";

  // Sticky nav background on scroll
  var nav = document.getElementById("nav");
  var onScroll = function () {
    if (window.scrollY > 40) {
      nav.classList.add("is-scrolled");
    } else {
      nav.classList.remove("is-scrolled");
    }
  };
  document.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile menu toggle
  var toggle = document.getElementById("navToggle");
  var menu = document.getElementById("navMenu");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        menu.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // Scroll-triggered reveal
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  // Fluid mouse-tracking ambient cloud effect with organic momentum & breathing flow
  var blobs = document.querySelectorAll(".glow-blob");
  if (blobs.length && !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    var mouseX = window.innerWidth / 2;
    var mouseY = window.innerHeight / 2;
    var targetX = window.innerWidth / 2;
    var targetY = window.innerHeight / 2;

    document.addEventListener("mousemove", function (e) {
      targetX = e.clientX;
      targetY = e.clientY;
    }, { passive: true });

    function animateBlobs() {
      // Linear interpolation (lerp) for smooth weighted lagging momentum
      mouseX += (targetX - mouseX) * 0.04;
      mouseY += (targetY - mouseY) * 0.04;

      var centerX = window.innerWidth / 2;
      var centerY = window.innerHeight / 2;
      var moveX = mouseX - centerX;
      var moveY = mouseY - centerY;
      var time = Date.now() * 0.0007; // Organic breathing speed

      blobs.forEach(function (blob, i) {
        var speed = parseFloat(blob.getAttribute("data-speed")) || 0.03;
        
        // Continuous sine/cosine wave flow for independent ambient breathing
        var ambientX = Math.sin(time + (i * 2.2)) * 40;
        var ambientY = Math.cos(time + (i * 1.8)) * 40;

        // Combined cursor pull and organic sine drift
        var x = (moveX * speed * 1.4) + ambientX;
        var y = (moveY * speed * 1.4) + ambientY;

        blob.style.transform = "translate(" + x + "px, " + y + "px)";
      });

      requestAnimationFrame(animateBlobs);
    }

    requestAnimationFrame(animateBlobs);
  }

  // Single-line vertical ticker (Studio section engineering list)
  var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("[data-ticker]").forEach(function (root) {
    var track = root.querySelector("[data-ticker-track]");
    var viewport = root.querySelector(".ticker-viewport");
    var dotsWrap = root.querySelector("[data-ticker-dots]");
    if (!track || !viewport) return;

    var items = Array.prototype.slice.call(track.children);
    var count = items.length;
    if (count < 2) return;

    if (reducedMotion) {
      root.classList.add("is-static");
      return;
    }

    // Build progress dots
    var dots = [];
    if (dotsWrap) {
      items.forEach(function (_, i) {
        var d = document.createElement("span");
        d.className = "ticker-dot" + (i === 0 ? " is-active" : "");
        dotsWrap.appendChild(d);
        dots.push(d);
      });
    }

    // Duplicate the first row at the end for a seamless wrap-around
    var clone = items[0].cloneNode(true);
    clone.setAttribute("aria-hidden", "true");
    track.appendChild(clone);

    var index = 0;
    var rowHeight = 0;

    function measure() {
      items.forEach(function (li) { li.style.height = ""; });
      clone.style.height = "";

      rowHeight = items.reduce(function (max, li) {
        return Math.max(max, li.getBoundingClientRect().height);
      }, 0);

      items.forEach(function (li) { li.style.height = rowHeight + "px"; });
      clone.style.height = rowHeight + "px";

      viewport.style.height = rowHeight + "px";
      track.classList.add("no-transition");
      track.style.transform = "translateY(-" + index * rowHeight + "px)";
      track.offsetHeight;
      track.classList.remove("no-transition");
    }

    function setActiveDot(i) {
      if (!dots.length) return;
      dots.forEach(function (d) { d.classList.remove("is-active"); });
      dots[i % count].classList.add("is-active");
    }

    function advance() {
      index++;
      track.style.transform = "translateY(-" + index * rowHeight + "px)";
      setActiveDot(index);

      if (index === count) {
        track.addEventListener("transitionend", function snapBack() {
          track.removeEventListener("transitionend", snapBack);
          track.classList.add("no-transition");
          index = 0;
          track.style.transform = "translateY(0)";
          track.offsetHeight;
          track.classList.remove("no-transition");
        }, { once: true });
      }
    }

    measure();

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(measure);
    }
    window.setTimeout(measure, 1200);

    var timer = window.setInterval(advance, 3800);

    var resizeTimeout;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(measure, 150);
    });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        clearInterval(timer);
      } else {
        timer = window.setInterval(advance, 3800);
      }
    });
  });
})();

// Cloudflare Web Analytics
(function () {
  var beacon = document.createElement("script");
  beacon.type = "module";
  beacon.src = "https://static.cloudflareinsights.com/beacon.min.js";
  beacon.setAttribute("data-cf-beacon", '{"token": "0c23be45c4a0464aa7a467bf9286dfa2"}');
  document.head.appendChild(beacon);
})();
