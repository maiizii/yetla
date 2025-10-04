(function () {
  const THEME_STORAGE_KEY = "yetla-admin-theme";
  const AVAILABLE_THEMES = ["aurora", "nebula"];
  const DEFAULT_THEME = "aurora";
  const RANDOM_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const COPY_FEEDBACK_TIMEOUT = 2000;
  let storedThemeValue = null;

  function onReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function createFragment(html) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    return template.content;
  }

  function swapContent(target, html, swap) {
    if (!target) {
      return;
    }

    if (swap === "outerHTML") {
      if (html.trim() === "") {
        target.outerHTML = html;
        enhanceDynamicUI();
        return;
      }
      const fragment = createFragment(html);
      const firstElement = fragment.firstElementChild;
      if (firstElement) {
        target.replaceWith(firstElement);
        enhanceDynamicUI(firstElement);
      } else {
        target.outerHTML = html;
        enhanceDynamicUI();
      }
      return;
    }

    target.innerHTML = html;
    enhanceDynamicUI(target);
  }

  function resolveTarget(element, selector) {
    if (!selector) {
      return null;
    }

    if (selector.startsWith("closest ")) {
      const actual = selector.replace("closest ", "").trim();
      if (!actual) {
        return null;
      }
      return element.closest(actual);
    }

    return document.querySelector(selector);
  }

  function buildHeaders(authHeader, extra) {
    const headers = {
      "HX-Request": "true",
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    };

    if (authHeader) {
      headers.Authorization = authHeader;
    }

    return Object.assign(headers, extra || {});
  }

  function toAbsoluteUrl(url) {
    if (!url) {
      return url;
    }

    try {
      const base = `${window.location.protocol}//${window.location.host}`;
      return new URL(url, base).toString();
    } catch (error) {
      console.warn("Failed to construct absolute URL", url, error);
      return url;
    }
  }

  async function fetchFragment(url, options) {
    const absoluteUrl = toAbsoluteUrl(url);
    const response = await fetch(
      absoluteUrl,
      Object.assign({ credentials: "include" }, options),
    );
    const text = await response.text();
    return { response, text };
  }

  async function submitWithFallback(formLike, submitter, authHeaderValue) {
    if (!(formLike instanceof HTMLFormElement)) {
      return;
    }

    if (
      !formLike.hasAttribute("hx-post") &&
      !formLike.hasAttribute("hx-put")
    ) {
      return;
    }

    if (formLike.dataset.htmxSubmitting === "true") {
      return;
    }

    const targetUrl =
      formLike.getAttribute("hx-post") || formLike.getAttribute("hx-put");
    if (!targetUrl) {
      return;
    }

    formLike.dataset.htmxSubmitting = "true";

    const method = formLike.hasAttribute("hx-post") ? "POST" : "PUT";
    const targetSelector = formLike.getAttribute("hx-target");
    const swapStrategy = formLike.getAttribute("hx-swap") || "innerHTML";
    const target = resolveTarget(formLike, targetSelector);

    bindDomainInputs(formLike);

    const formData = new FormData(formLike);
    if (
      submitter &&
      typeof submitter.name === "string" &&
      submitter.name &&
      !formData.has(submitter.name)
    ) {
      formData.append(submitter.name, submitter.value);
    }

    const body = new URLSearchParams();
    formData.forEach((value, key) => {
      if (typeof value === "string") {
        body.append(key, value);
      }
    });

    try {
      const { response, text } = await fetchFragment(targetUrl, {
        method,
        headers: buildHeaders(authHeaderValue, {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }),
        body,
      });

      if (target) {
        swapContent(target, text, swapStrategy);
      }

      if (response.ok) {
        handleSuccess(formLike);
      }
    } catch (error) {
      if (target) {
        target.textContent = "请求失败，请稍后再试";
      }
      console.error("Failed to submit form", error);
    } finally {
      delete formLike.dataset.htmxSubmitting;
    }
  }

  function dispatchSuccessEvent(element) {
    const eventName = element.getAttribute("data-success-event");
    if (!eventName) {
      return;
    }

    if (window.htmx && typeof window.htmx.trigger === "function") {
      window.htmx.trigger(document.body, eventName);
      return;
    }

    document.body.dispatchEvent(new CustomEvent(eventName, { bubbles: true }));
  }

  function handleSuccess(formLike) {
    if (formLike instanceof HTMLFormElement) {
      if (formLike.getAttribute("data-reset-on-success") === "true") {
        formLike.reset();
      }
      applyPostSuccessEnhancements(formLike);
    }
    dispatchSuccessEvent(formLike);
  }

  async function refreshLinks(authHeader) {
    const countAnchor = document.getElementById("short-link-count");
    if (countAnchor) {
      try {
        const { response, text } = await fetchFragment("/admin/links/count", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(countAnchor, text, "outerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh short link count", error);
      }
    }

    const tableContainer = document.getElementById("links-table");
    if (tableContainer) {
      try {
        const { response, text } = await fetchFragment("/admin/links/table", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(tableContainer, text, "innerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh short link table", error);
      }
    }
  }

  async function refreshSubdomains(authHeader) {
    const countAnchor = document.getElementById("subdomain-count");
    if (countAnchor) {
      try {
        const { response, text } = await fetchFragment("/admin/subdomains/count", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(countAnchor, text, "outerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh subdomain count", error);
      }
    }

    const tableContainer = document.getElementById("subdomains-table");
    if (tableContainer) {
      try {
        const { response, text } = await fetchFragment("/admin/subdomains/table", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(tableContainer, text, "innerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh subdomain table", error);
      }
    }
  }

  function highlightThemeCards(activeTheme, previewTheme) {
    const cards = document.querySelectorAll("[data-theme-option]");
    cards.forEach((card) => {
      const option = card.getAttribute("data-theme-option");
      const isActive = option === activeTheme;
      const isPreview = previewTheme && option === previewTheme;
      card.classList.toggle("is-active", Boolean(isActive));
      card.classList.toggle("is-preview", Boolean(isPreview) && !isActive);

      const applyButton = card.querySelector("[data-theme-apply]");
      if (applyButton) {
        applyButton.setAttribute("aria-pressed", isActive ? "true" : "false");
      }
    });
  }

  function sanitizeTheme(theme) {
    if (!theme) {
      return DEFAULT_THEME;
    }
    return AVAILABLE_THEMES.includes(theme) ? theme : DEFAULT_THEME;
  }

  function highlightThemeToggles(activeTheme) {
    const toggles = document.querySelectorAll("[data-theme-toggle]");
    toggles.forEach((toggle) => {
      const target = toggle.getAttribute("data-theme-toggle");
      const isActive = target === activeTheme;
      toggle.classList.toggle("is-active", Boolean(isActive));
      toggle.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function setTheme(theme, { persist = false, preview = false } = {}) {
    const targetTheme = sanitizeTheme(theme);

    const root = document.documentElement;
    const body = document.body;

    if (root) {
      root.setAttribute("data-theme", targetTheme);
    }
    if (body) {
      body.setAttribute("data-theme", targetTheme);
    }

    if (persist) {
      storedThemeValue = targetTheme;
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, targetTheme);
      } catch (error) {
        /* ignore storage failures */
      }
    }

    const activeTheme = storedThemeValue || targetTheme;
    highlightThemeCards(activeTheme, preview ? targetTheme : undefined);
    highlightThemeToggles(activeTheme);
  }

  function getStoredTheme() {
    if (storedThemeValue) {
      return sanitizeTheme(storedThemeValue);
    }

    let saved = DEFAULT_THEME;
    try {
      const fromStorage = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (fromStorage) {
        saved = sanitizeTheme(fromStorage);
      } else {
        const attr = document.documentElement.getAttribute("data-theme");
        if (attr) {
          saved = sanitizeTheme(attr);
        }
      }
    } catch (error) {
      const attr = document.documentElement.getAttribute("data-theme");
      if (attr) {
        saved = sanitizeTheme(attr);
      }
    }

    storedThemeValue = saved;
    return saved;
  }

  function restorePersistedTheme() {
    const theme = getStoredTheme();
    setTheme(theme, { persist: false });
  }

  function bindThemeToggles() {
    const toggles = document.querySelectorAll("[data-theme-toggle]");

    if (!toggles.length) {
      return;
    }

    toggles.forEach((toggle) => {
      if (toggle.dataset.themeToggleBound === "true") {
        return;
      }
      toggle.dataset.themeToggleBound = "true";
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        const targetTheme = sanitizeTheme(toggle.getAttribute("data-theme-toggle"));
        setTheme(targetTheme, { persist: true });
      });
    });

    highlightThemeToggles(getStoredTheme());
  }

  function bindThemeGallery() {
    const cards = Array.from(
      document.querySelectorAll("[data-theme-option]"),
    );

    if (!cards.length) {
      return;
    }

    const handleApply = (event) => {
      const button = event.currentTarget;
      const theme = button.getAttribute("data-theme-apply");
      if (!theme) {
        return;
      }
      event.preventDefault();
      setTheme(theme, { persist: true });
    };

    cards.forEach((card) => {
      const theme = card.getAttribute("data-theme-option");
      const applyButton = card.querySelector("[data-theme-apply]");

      if (applyButton) {
        applyButton.addEventListener("click", handleApply);
      }

      card.addEventListener("mouseenter", () => {
        if (theme) {
          setTheme(theme, { preview: true });
        }
      });

      card.addEventListener("mouseleave", () => {
        const saved = getStoredTheme();
        setTheme(saved, { persist: false });
      });

      card.addEventListener("click", (event) => {
        if (event.target.closest("[data-theme-apply]")) {
          return;
        }
        if (theme) {
          setTheme(theme, { persist: true });
        }
      });

      card.addEventListener("focusin", () => {
        if (theme) {
          setTheme(theme, { preview: true });
        }
      });

      card.addEventListener("focusout", () => {
        const saved = getStoredTheme();
        setTheme(saved, { persist: false });
      });

      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          if (!theme) {
            return;
          }
          event.preventDefault();
          setTheme(theme, { persist: true });
        }
      });
    });

    const saved = getStoredTheme();
    highlightThemeCards(saved);
  }

  function bindDomainInputs(root = document) {
    const scope = root instanceof Element ? root : document;
    const groups = scope.querySelectorAll("[data-domain-input]");

    groups.forEach((group) => {
      if (!(group instanceof HTMLElement)) {
        return;
      }

      if (group.dataset.domainEnhanced === "true") {
        if (typeof group.__updateDomainValue === "function") {
          group.__updateDomainValue();
        }
        return;
      }

      const input = group.querySelector("[data-domain-input-field]");
      const hidden = group.querySelector("[data-domain-input-hidden]");
      const rawSuffix = group.getAttribute("data-domain-suffix") || "";
      const suffix = rawSuffix.trim();

      const updateValue = () => {
        if (!hidden) {
          return;
        }

        if (!input) {
          hidden.value = suffix;
          return;
        }

        let prefixValue = input.value.trim();
        if (prefixValue) {
          const normalized = prefixValue.toLowerCase();
          if (normalized !== prefixValue) {
            input.value = normalized;
          }
          prefixValue = normalized;
        }

        let fullValue = "";
        if (suffix) {
          fullValue = prefixValue ? `${prefixValue}.${suffix}` : "";
        } else {
          fullValue = prefixValue;
        }

        hidden.value = fullValue;
      };

      if (input) {
        input.addEventListener("input", updateValue);
      }

      const form = group.closest("form");
      if (form) {
        form.addEventListener("reset", () => {
          window.setTimeout(updateValue, 0);
        });
      }

      group.dataset.domainEnhanced = "true";
      group.__updateDomainValue = updateValue;
      updateValue();
    });
  }

  function generateRandomCode(length) {
    const parsed = Number.parseInt(length, 10);
    const effectiveLength = Number.isFinite(parsed) && parsed > 0 ? parsed : 6;
    let result = "";
    for (let index = 0; index < effectiveLength; index += 1) {
      const randomIndex = Math.floor(Math.random() * RANDOM_CODE_ALPHABET.length);
      result += RANDOM_CODE_ALPHABET.charAt(randomIndex);
    }
    return result;
  }

  function bindCopyButtons(root = document) {
    const scope = root instanceof Element ? root : document;
    const buttons = scope.querySelectorAll("[data-copy-value]");

    buttons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      if (button.dataset.copyBound === "true") {
        return;
      }

      let timeoutId;

      const showFeedback = () => {
        button.classList.add("is-copied");
        clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => {
          button.classList.remove("is-copied");
        }, COPY_FEEDBACK_TIMEOUT);
      };

      const fallbackCopy = (value) => {
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.setAttribute("readonly", "true");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      };

      button.addEventListener("click", async (event) => {
        event.preventDefault();
        const value = button.getAttribute("data-copy-value") || "";
        if (!value) {
          return;
        }

        try {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            await navigator.clipboard.writeText(value);
          } else {
            fallbackCopy(value);
          }
          showFeedback();
        } catch (error) {
          try {
            fallbackCopy(value);
            showFeedback();
          } catch (fallbackError) {
            console.warn("Failed to copy value", fallbackError);
          }
        }
      });

      button.dataset.copyBound = "true";
    });
  }

  function applyPostSuccessEnhancements(formLike) {
    if (!(formLike instanceof HTMLFormElement)) {
      return;
    }

    const domainGroups = formLike.querySelectorAll("[data-domain-input]");
    domainGroups.forEach((group) => {
      if (group && typeof group.__updateDomainValue === "function") {
        group.__updateDomainValue();
      }
    });

    const randomInputs = formLike.querySelectorAll("[data-random-code='true']");
    randomInputs.forEach((input) => {
      if (!(input instanceof HTMLInputElement)) {
        return;
      }
      const length = input.getAttribute("data-random-code-length") || "6";
      const nextValue = generateRandomCode(length);
      input.value = nextValue;
      input.defaultValue = nextValue;
    });
  }

  function enhanceDynamicUI(root) {
    bindDomainInputs(root);
    bindCopyButtons(root);
  }

  onReady(() => {
    const authHeader = document.body.dataset.authHeader || "";
    const useFallback = typeof window.htmx === "undefined";

    restorePersistedTheme();
    bindThemeToggles();
    bindThemeGallery();
    enhanceDynamicUI();

    if (!useFallback) {
      document.body.addEventListener("htmx:afterSwap", (event) => {
        const target = event.target;
        if (target instanceof HTMLElement) {
          enhanceDynamicUI(target);
        } else {
          enhanceDynamicUI();
        }
      });
      document.body.addEventListener("htmx:configRequest", (event) => {
        const source = event.target;
        if (!(source instanceof HTMLElement)) {
          return;
        }
        const form = source.closest("form");
        if (form) {
          bindDomainInputs(form);
        }
      });
      document.body.addEventListener("htmx:afterRequest", (event) => {
        const detail = event.detail || {};
        const { successful, xhr } = detail;
        const status = xhr && typeof xhr.status === "number" ? xhr.status : 0;
        const isSuccessful =
          typeof successful === "boolean"
            ? successful
            : status >= 200 && status < 400;
        if (!isSuccessful) {
          return;
        }
        const source = event.target;
        if (!(source instanceof HTMLElement)) {
          return;
        }

        const target = source.closest("[data-success-event]") || source;
        if (target instanceof HTMLElement) {
          handleSuccess(target);
        }
      });
      return;
    }

    console.warn(
      "htmx 未加载，使用回退逻辑处理短链子域管理后台交互。\n建议检查 CDN 是否可访问。"
    );

    const refreshLinksHandler = () => refreshLinks(authHeader);
    const refreshSubdomainsHandler = () => refreshSubdomains(authHeader);

    document.body.addEventListener("refresh-links", refreshLinksHandler);
    document.body.addEventListener("refresh-subdomains", refreshSubdomainsHandler);

    refreshLinksHandler();
    refreshSubdomainsHandler();

    document.body.addEventListener("submit", async (event) => {
      const form =
        event.target instanceof HTMLFormElement
          ? event.target
          : event.target.closest("form");
      if (!form) {
        return;
      }

      if (form.dataset.htmxSubmitting === "true") {
        event.preventDefault();
        return;
      }

      if (!form.hasAttribute("hx-post") && !form.hasAttribute("hx-put")) {
        return;
      }

      event.preventDefault();

      const submitter =
        typeof event.submitter !== "undefined" && event.submitter
          ? event.submitter
          : undefined;
      await submitWithFallback(form, submitter, authHeader);
    });

    document.body.addEventListener("click", async (event) => {
      const submitter = event.target.closest(
        "button[type=submit], input[type=submit]",
      );
      if (submitter) {
        const form = submitter.form || submitter.closest("form");
        if (form) {
          if (form.dataset.htmxSubmitting === "true") {
            event.preventDefault();
            return;
          }
          if (form.hasAttribute("hx-post") || form.hasAttribute("hx-put")) {
            event.preventDefault();
            await submitWithFallback(form, submitter, authHeader);
            return;
          }
        }
      }

      const trigger = event.target.closest("[hx-get], [hx-delete]");
      if (!trigger) {
        return;
      }

      const isGet = trigger.hasAttribute("hx-get");
      const isDelete = trigger.hasAttribute("hx-delete");

      if (isDelete) {
        const message = trigger.getAttribute("hx-confirm");
        if (message && !window.confirm(message)) {
          return;
        }
      }

      event.preventDefault();

      const url = trigger.getAttribute(isGet ? "hx-get" : "hx-delete");
      const targetSelector = trigger.getAttribute("hx-target");
      const swapStrategy = trigger.getAttribute("hx-swap") || "innerHTML";
      const target = resolveTarget(trigger, targetSelector);

      try {
        const { response, text } = await fetchFragment(url, {
          method: isDelete ? "DELETE" : "GET",
          headers: buildHeaders(authHeader),
        });

        if (target) {
          swapContent(target, text, swapStrategy);
        }

        if (response.ok && !isGet) {
          // 删除操作会触发刷新事件
          handleSuccess(trigger);
        }
      } catch (error) {
        if (target) {
          target.textContent = "请求失败，请稍后再试";
        }
        console.error("Failed to process request", error);
      }
    });
  });
})();
