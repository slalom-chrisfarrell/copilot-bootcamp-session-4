document.addEventListener("DOMContentLoaded", () => {
  const capabilitiesList = document.getElementById("capabilities-list");
  const capabilitySelect = document.getElementById("capability");
  const registerForm = document.getElementById("register-form");
  const messageDiv = document.getElementById("message");
  const authButton = document.getElementById("auth-button");
  const authStatus = document.getElementById("auth-status");
  const authModal = document.getElementById("auth-modal");
  const authForm = document.getElementById("auth-form");
  const authCancel = document.getElementById("auth-cancel");

  const AUTH_TOKEN_KEY = "slalom_auth_token";
  let authToken = localStorage.getItem(AUTH_TOKEN_KEY);
  let currentUser = null;

  function authHeaders() {
    return authToken ? { Authorization: `Bearer ${authToken}` } : {};
  }

  function setMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function openAuthModal() {
    authModal.classList.remove("hidden");
  }

  function closeAuthModal() {
    authModal.classList.add("hidden");
    authForm.reset();
  }

  async function refreshAuthStatus() {
    if (!authToken) {
      currentUser = null;
      authStatus.textContent = "Signed out";
      authButton.textContent = "Practice Lead Login";
      return;
    }

    try {
      const response = await fetch("/auth/me", {
        headers: authHeaders(),
      });
      const result = await response.json();

      if (!result.authenticated) {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        authToken = null;
        currentUser = null;
        authStatus.textContent = "Signed out";
        authButton.textContent = "Practice Lead Login";
        return;
      }

      currentUser = result;
      authStatus.textContent = `Signed in as ${result.username}`;
      authButton.textContent = "Sign Out";
    } catch (error) {
      console.error("Error checking auth status:", error);
      currentUser = null;
      authStatus.textContent = "Signed out";
      authButton.textContent = "Practice Lead Login";
    }
  }

  // Function to fetch capabilities from API
  async function fetchCapabilities() {
    try {
      const response = await fetch("/capabilities");
      const capabilities = await response.json();

      // Clear loading message
      capabilitiesList.innerHTML = "";
      capabilitySelect.innerHTML =
        '<option value="">-- Select a capability --</option>';

      // Populate capabilities list
      Object.entries(capabilities).forEach(([name, details]) => {
        const capabilityCard = document.createElement("div");
        capabilityCard.className = "capability-card";

        const availableCapacity = details.capacity || 0;
        const currentConsultants = details.consultants ? details.consultants.length : 0;

        // Create consultants HTML with delete icons
        const canManageConsultants =
          currentUser && currentUser.role === "practice_lead";

        const consultantsHTML =
          details.consultants && details.consultants.length > 0
            ? `<div class="consultants-section">
              <h5>Registered Consultants:</h5>
              <ul class="consultants-list">
                ${details.consultants
                  .map(
                    (email) =>
                      `<li><span class="consultant-email">${email}</span>${
                        canManageConsultants
                          ? `<button class="delete-btn" data-capability="${name}" data-email="${email}" aria-label="Remove ${email}">Remove</button>`
                          : ""
                      }</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No consultants registered yet</em></p>`;

        capabilityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Practice Area:</strong> ${details.practice_area}</p>
          <p><strong>Industry Verticals:</strong> ${details.industry_verticals ? details.industry_verticals.join(', ') : 'Not specified'}</p>
          <p><strong>Capacity:</strong> ${availableCapacity} hours/week available</p>
          <p><strong>Current Team:</strong> ${currentConsultants} consultants</p>
          <div class="consultants-container">
            ${consultantsHTML}
          </div>
        `;

        capabilitiesList.appendChild(capabilityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        capabilitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      capabilitiesList.innerHTML =
        "<p>Failed to load capabilities. Please try again later.</p>";
      console.error("Error fetching capabilities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    if (!currentUser || currentUser.role !== "practice_lead") {
      setMessage("Only practice leads can unregister consultants.", "error");
      return;
    }

    const button = event.target;
    const capability = button.getAttribute("data-capability");
    const email = button.getAttribute("data-email");

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
          headers: {
            ...authHeaders(),
          },
        }
      );

      const result = await response.json();

      if (response.ok) {
        setMessage(result.message, "success");

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
      } else {
        setMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      setMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  // Handle form submission
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const capability = document.getElementById("capability").value;

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/register?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        setMessage(result.message, "success");
        registerForm.reset();

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
      } else {
        setMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      setMessage("Failed to register. Please try again.", "error");
      console.error("Error registering:", error);
    }
  });

  authButton.addEventListener("click", async () => {
    if (authToken) {
      try {
        await fetch("/auth/logout", {
          method: "POST",
          headers: authHeaders(),
        });
      } catch (error) {
        console.error("Error during logout:", error);
      }

      localStorage.removeItem(AUTH_TOKEN_KEY);
      authToken = null;
      currentUser = null;
      await refreshAuthStatus();
      await fetchCapabilities();
      setMessage("Signed out successfully.", "info");
      return;
    }

    openAuthModal();
  });

  authCancel.addEventListener("click", () => {
    closeAuthModal();
  });

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const result = await response.json();
      if (!response.ok) {
        setMessage(result.detail || "Login failed.", "error");
        return;
      }

      authToken = result.token;
      localStorage.setItem(AUTH_TOKEN_KEY, authToken);
      closeAuthModal();
      await refreshAuthStatus();
      await fetchCapabilities();
      setMessage(`Welcome, ${result.username}.`, "success");
    } catch (error) {
      setMessage("Failed to sign in. Please try again.", "error");
      console.error("Error signing in:", error);
    }
  });

  // Initialize app
  refreshAuthStatus().then(fetchCapabilities);
});
