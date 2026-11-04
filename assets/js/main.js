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

  // Mouse following for logo/blob
  var animElements = document.querySelectorAll(".glow-blob, .floating-logo-graphic");
  var motionQuery = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;
  var ambientFrame = null;

  if (animElements.length && !(motionQuery && motionQuery.matches)) {
    var mouseX = window.innerWidth / 2;
    var mouseY = window.innerHeight / 2;
    var targetX = mouseX;
    var targetY = mouseY;
    var lastTime = 0;

    document.addEventListener("mousemove", function (event) {
      targetX = event.clientX;
      targetY = event.clientY;
    }, { passive: true });

    function animateAmbient(timestamp) {
      if (document.hidden || (motionQuery && motionQuery.matches)) {
        ambientFrame = null;
        return;
      }

      var delta = lastTime ? Math.min(timestamp - lastTime, 32) : 16;
      lastTime = timestamp;
      var easing = 1 - Math.pow(1 - 0.04, delta / 16.67);

      mouseX += (targetX - mouseX) * easing;
      mouseY += (targetY - mouseY) * easing;

      var moveX = mouseX - window.innerWidth / 2;
      var moveY = mouseY - window.innerHeight / 2;
      var time = timestamp * 0.00018;

      animElements.forEach(function (element, index) {
        var isLogo = element.classList.contains("floating-logo-graphic");
        var speed = parseFloat(element.getAttribute("data-speed")) || (isLogo ? 1.0 : 0.03);
        var phase = index * 2.1;
        var ambientX = isLogo ? 0 : Math.sin(time + phase) * 22;
        var ambientY = isLogo ? 0 : Math.cos(time * 0.9 + phase) * 22;
        var x = moveX * speed + ambientX;
        var y = moveY * speed + ambientY;

        element.style.setProperty("--float-x", x.toFixed(2) + "px");
        element.style.setProperty("--float-y", y.toFixed(2) + "px");

        // Apply direct transform so it follows the mouse fully
        if (element.classList.contains("glow-blob") || isLogo) {
          element.style.transform = "translate3d(" +
            x.toFixed(2) + "px, " + y.toFixed(2) + "px, 0)";
        }
      });

      ambientFrame = window.requestAnimationFrame(animateAmbient);
    }

    function startAmbientAnimation() {
      if (!ambientFrame && !document.hidden && !(motionQuery && motionQuery.matches)) {
        lastTime = 0;
        ambientFrame = window.requestAnimationFrame(animateAmbient);
      }
    }

    function stopAmbientAnimation() {
      if (ambientFrame) {
        window.cancelAnimationFrame(ambientFrame);
        ambientFrame = null;
      }
    }

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        stopAmbientAnimation();
      } else {
        startAmbientAnimation();
      }
    });

    if (motionQuery) {
      var onMotionPreferenceChange = function (event) {
        if (event.matches) {
          stopAmbientAnimation();
          animElements.forEach(function (element) {
            element.style.removeProperty("--float-x");
            element.style.removeProperty("--float-y");
            element.style.transform = "";
          });
        } else {
          startAmbientAnimation();
        }
      };

      if (motionQuery.addEventListener) {
        motionQuery.addEventListener("change", onMotionPreferenceChange);
      } else if (motionQuery.addListener) {
        motionQuery.addListener(onMotionPreferenceChange);
      }
    }

    startAmbientAnimation();
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

    var dots = [];
    if (dotsWrap) {
      items.forEach(function (_, i) {
        var d = document.createElement("span");
        d.className = "ticker-dot" + (i === 0 ? " is-active" : "");
        dotsWrap.appendChild(d);
        dots.push(d);
      });
    }

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
