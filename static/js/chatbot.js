/**
 * Invoice Chatbot Handler
 * Handles all chatbot UI interactions and API calls
 *
 * Dependencies:
 * - Bootstrap 5 (for modal/toast)
 * - Requires CSRF token in page
 *
 * Usage:
 * <script src="{{ url_for('static', filename='js/chatbot.js') }}"></script>
 */

class InvoiceChatbot {
  constructor() {
    this.conversationId = null;
    this.apiUrl = "/api/chat";
    this.chatBody = document.getElementById("chat-body");
    this.chatInput = document.getElementById("chat-input");
    this.sendBtn = document.getElementById("send-btn");
    this.chatWindow = document.getElementById("chat-window");
    this.chatFab = document.getElementById("chat-fab");
    this.voiceBtn = document.getElementById("voice-btn");
    this.isListening = false;
    this.recognition = null;

    this.init();
  }

  init() {
    console.log("🤖 Chatbot initialized");

    // Initialize welcome message
    this.initializeChat();

    // Set up event listeners
    if (this.chatInput && this.sendBtn) {
      this.chatInput.addEventListener("input", () => {
        const hasText = this.chatInput.value.trim() !== "";
        this.sendBtn.style.display = hasText ? "flex" : "none";
        this.voiceBtn.style.display = hasText ? "none" : "flex";
      });

      this.chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && this.sendBtn.style.display !== "none") {
          this.sendMessage();
        }
      });
      this.sendBtn.addEventListener("click", () => this.sendMessage());
      this.voiceBtn.addEventListener("click", () => this.toggleVoice());

      // Initially disable send button
      this.sendBtn.style.display = "none";   // hide send, show mic by default
      this.voiceBtn.style.display = "flex";
    }
  }

  initializeChat() {
    if (!this.chatBody) return;

    const botImgPath = "/static/images/invoice_chatbot.png"; // Adjust if needed

    const welcomeHTML = `
      <div class="welcome-date">Today</div>
      <div class="message-wrapper bot-message">
        <div class="message-avatar">
          <img src="${botImgPath}" alt="Bot">
        </div>
        <div>
          <div class="message-bubble">
            Hello! I'm InvoiceBot. I can help you with:<br><br>
            • Pending invoices<br>
            • Vendor information<br>
            • Payment tracking<br>
            • Monthly spending reports
          </div>
          <div class="quick-replies">
            <button class="quick-reply-btn" onclick="chatbot.handleQuickReply('Show pending invoices')">
              📋 Show Pending Invoices
            </button>
            <button class="quick-reply-btn" onclick="chatbot.handleQuickReply('What is the total budget consumed for this month? ')">
              💰 Current Month Spend
            </button>
            <button class="quick-reply-btn" onclick="chatbot.handleQuickReply('List all vendors')">
              🏢 All Vendors
            </button>
          </div>
        </div>
      </div>
    `;

    this.chatBody.innerHTML = welcomeHTML;
  }

  handleQuickReply(message) {
    if (this.chatInput) {
      this.chatInput.value = message;
      this.sendMessage();
    }
  }

  async sendMessage() {
    const message = this.chatInput.value.trim();
    if (!message) return;

    this.chatInput.disabled = true;
    this.sendBtn.disabled = true;

    // Add user message to UI
    this.addMessageToChat(message, "user");
    this.chatInput.value = "";

    // Show typing indicator
    this.showTypingIndicator();

    try {
      // Get CSRF token (try hidden input first, then meta tag)
      const csrfInput = document.querySelector('input[name="csrf_token"]');
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfInput?.value || csrfMeta?.getAttribute("content");

      if (!csrfToken) {
        throw new Error("CSRF token not found");
      }

      // Call API
      const useV2 = true;
      const apiURL = useV2 ? "/api/chat/v2" : "/api/chat";

      const response = await fetch(apiURL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "include",
        body: JSON.stringify({
          message: message,
          conversation_id: this.conversationId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.removeTypingIndicator();

      // ALWAYS save conversation_id if present (needed for clarification flow!)
      if (data.needs_clarification) {
        this.conversationId = data.conversation_id;
      }else{
        this.conversationId = null;
      }

      if (data.needs_clarification) {
        if (data.clarification_type === "entity_selection") {
          this.showEntitySelector(data);
          return;
        } else if (data.clarification_type === "date_range") {
          this.showDateRangePicker(data);
          return;
        }
        // For other clarification types, show the message as bot response
        if (data.response) {
          const formattedResponse = this.formatBotResponse(data.response);
          this.addMessageToChat(formattedResponse, "bot");
        }
        return;
      }

      if (data.success || !data.error) {
        const formattedResponse = this.formatBotResponse(data.response);
        this.addMessageToChat(formattedResponse, "bot");
      } else {
        this.addMessageToChat(
          data.response || "Sorry, something went wrong. Please try again.",
          "bot",
        );
      }
    } catch (error) {
      console.error("❌ Chat error:", error);
      this.removeTypingIndicator();
      this.addMessageToChat(
        "Sorry, I encountered an error. Please check your connection and try again.",
        "bot",
      );
    } finally {
      this.chatInput.disabled = false;
      this.sendBtn.disabled = false;
      if (this.chatInput.value.trim() === "") {
        this.sendBtn.style.display = "none";
        this.voiceBtn.style.display = "flex";
      } else {
        this.sendBtn.style.display = "flex";
        this.voiceBtn.style.display = "none";
      }
      this.chatInput.focus();
    }
  }

  formatBotResponse(text) {
    // Format bold text
    text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Format line breaks
    text = text.replace(/\n/g, "<br>");

    // Format numbers with commas (optional)
    // text = text.replace(/(\d+)/g, (match) => {
    //   return match.length > 3 ? match.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : match;
    // });

    return text;
  }

  addMessageToChat(text, sender) {
    if (!this.chatBody) return;

    const botImgPath = "/static/images/invoice_chatbot.png";
    let messageHTML = `<div class="message-wrapper ${sender}-message">`;

    if (sender === "bot") {
      messageHTML += `
        <div class="message-avatar">
          <img src="${botImgPath}" alt="Bot">
        </div>
      `;
    }

    messageHTML += `
      <div>
        <div class="message-bubble">${text}</div>
      </div>
    </div>`;

    this.chatBody.insertAdjacentHTML("beforeend", messageHTML);
    this.scrollToBottom();
  }

  showTypingIndicator() {
    if (!this.chatBody) return;

    const botImgPath = "/static/images/invoice_chatbot.png";
    const typingHTML = `
      <div class="message-wrapper bot-message typing-wrapper">
        <div class="message-avatar">
          <img src="${botImgPath}" alt="Bot">
        </div>
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;

    this.chatBody.insertAdjacentHTML("beforeend", typingHTML);
    this.scrollToBottom();
  }

  removeTypingIndicator() {
    const typingWrapper = document.querySelector(".typing-wrapper");
    if (typingWrapper) {
      typingWrapper.remove();
    }
  }

  scrollToBottom() {
    if (this.chatBody) {
      this.chatBody.scrollTop = this.chatBody.scrollHeight;
    }
  }

  initVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("⚠️ Speech recognition not supported in this browser");
      return;
    }
    this.recognition = new SpeechRecognition();
    this.recognition.lang = "en-IN";       // Indian English — change to "en-US" if needed
    this.recognition.interimResults = true; // shows live preview while speaking
    this.recognition.continuous = false;    // stops after one sentence

    this.recognition.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
      // Show live preview in input box while speaking
      this.chatInput.value = final || interim;
      this.chatInput.dispatchEvent(new Event("input")); // triggers send/mic swap
    };

    this.recognition.onend = () => {
      const text = this.chatInput.value.trim();
      this.stopListening();
      if (text) {
        this.sendMessage(); // auto-send when voice ends
      }
    };

    this.recognition.onerror = (event) => {
      console.error("🎙️ Voice error:", event.error);
      this.stopListening();
      if (event.error === "not-allowed") {
        alert("Microphone access denied. Please allow microphone in browser settings.");
      }
    };
  }

  toggleVoice() {
    if (!this.recognition) {
      this.initVoice();
    }
    if (this.isListening) {
      this.recognition.stop();
    } else {
      this.startListening();
    }
  }

  startListening() {
    if (!this.recognition) return;
    this.isListening = true;
    this.voiceBtn.innerHTML = "🔴";          // red dot = recording
    this.voiceBtn.style.animation = "pulse 1s infinite";
    this.chatInput.placeholder = "Listening...";
    this.chatInput.value = "";
    this.recognition.start();
  }

  stopListening() {
    this.isListening = false;
    this.voiceBtn.innerHTML = "🎙️";          // back to mic icon
    this.voiceBtn.style.animation = "none";
    this.chatInput.placeholder = "Ask about invoices...";
  }

  showEntitySelector(data) {
    const entities = [];

    // Add vendors
    if (data.options?.vendors) {
      data.options.vendors.forEach((v) => {
        entities.push({
          type: "vendor",
          id: v.id,
          name: v.name,
          subtitle: v.shortform ? `(${v.shortform})` : "",
          preview: v.preview,
        });
      });
    }

    // Add users
    if (data.options?.users) {
      data.options.users.forEach((u) => {
        entities.push({
          type: "user",
          id: u.id,
          name: u.name,
          subtitle: u.email,
          preview: u.preview,
        });
      });
    }

    // Build HTML
    let html = `<div class="message-bubble">${data.message}</div>`;
    html += '<div class="entity-selector">';

    entities.forEach((entity) => {
      html += `
      <div class="entity-option" onclick="chatbot.selectEntity('${entity.type}', ${entity.id}, '${data.conversation_id}')">
        <strong>${entity.name}</strong> ${entity.subtitle}<br>
        <small>${entity.preview}</small>
      </div>
    `;
    });

    html += "</div>";

    this.addMessageToChat(html, "bot");
  }

  showDateRangePicker(data) {
    const entity = data.selected_entity;

    let html = `<div class="message-bubble">${data.message}</div>`;
    html += '<div class="date-range-picker">';

    // Quick picks
    if (data.date_options?.quick_picks) {
      data.date_options.quick_picks.forEach((option) => {
        html += `
        <button class="date-option-btn" 
                onclick="chatbot.selectDateRange('${option.value}', '${data.conversation_id}')">
          ${option.label}
        </button>
      `;
      });
    }

    html += "</div>";

    this.addMessageToChat(html, "bot");
  }

  async selectEntity(entityType, entityId, conversationId) {
    this.showTypingIndicator();

    try {
      const csrfInput = document.querySelector('input[name="csrf_token"]');
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfInput?.value || csrfMeta?.getAttribute("content");

      const response = await fetch("/api/chat/v2", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "include",
        body: JSON.stringify({
          conversation_id: conversationId,
          confirmation_data: {
            type: "entity_selection",
            entity_type: entityType,
            entity_id: entityId,
          },
        }),
      });

      const data = await response.json();
      this.removeTypingIndicator();

      // Handle next step (date range or results)
      if (
        data.needs_clarification &&
        data.clarification_type === "date_range"
      ) {
        this.showDateRangePicker(data);
      } else if (data.response) {
        this.addMessageToChat(data.response, "bot");
      }
    } catch (error) {
      console.error("Entity selection error:", error);
      this.removeTypingIndicator();
      this.addMessageToChat("Error processing selection.", "bot");
    }
  }

  async selectDateRange(quickPickValue, conversationId) {
    this.showTypingIndicator();

    try {
      const csrfInput = document.querySelector('input[name="csrf_token"]');
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfInput?.value || csrfMeta?.getAttribute("content");

      const response = await fetch("/api/chat/v2", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "include",
        body: JSON.stringify({
          conversation_id: conversationId,
          confirmation_data: {
            type: "date_range",
            date_range: quickPickValue,
          },
        }),
      });

      const data = await response.json();
      this.removeTypingIndicator();

      if (data.response) {
        this.addMessageToChat(data.response, "bot");
      }
    } catch (error) {
      console.error("Date range selection error:", error);
      this.removeTypingIndicator();
      this.addMessageToChat("Error processing date selection.", "bot");
    }
  }
}

// ============================================================================
// GLOBAL UTILITY FUNCTIONS (for backwards compatibility with HTML onclick)
// ============================================================================

function toggleChat() {
  const chatWindow = document.getElementById("chat-window");
  const chatFab = document.getElementById("chat-fab");

  if (!chatWindow || !chatFab) return;

  if (chatWindow.style.display === "none" || chatWindow.style.display === "") {
    chatWindow.style.display = "flex";
    chatFab.style.display = "none";
  } else {
    chatWindow.style.display = "none";
    chatFab.style.display = "flex";
  }
}

function minimizeChat() {
  const chatWindow = document.getElementById("chat-window");
  const chatFab = document.getElementById("chat-fab");

  if (chatWindow) chatWindow.style.display = "none";
  if (chatFab) chatFab.style.display = "flex";
}

function downloadConversation() {
  const chatBody = document.getElementById("chat-body");
  if (!chatBody) {
    alert("No conversation to download");
    return;
  }

  // Get all message bubbles
  const messages = chatBody.querySelectorAll(".message-wrapper");

  if (messages.length === 0) {
    alert("No messages to download");
    return;
  }

  // Build formatted text
  const now = new Date();
  const dateStr = now.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "long",
    day: "numeric"
  });
  const timeStr = now.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit"
  });

  let output = "";
  output += "═══════════════════════════════════════════════════════════\n";
  output += "           INVOICEBOT CONVERSATION TRANSCRIPT\n";
  output += "═══════════════════════════════════════════════════════════\n";
  output += `Date: ${dateStr}\n`;
  output += `Time: ${timeStr}\n`;
  output += "\n───────────────────────────────────────────────────────────\n\n";

  messages.forEach((msg) => {
    const isBot = msg.classList.contains("bot-message");
    const isUser = msg.classList.contains("user-message");

    // Skip typing indicators and quick replies
    if (msg.classList.contains("typing-wrapper")) return;

    const bubble = msg.querySelector(".message-bubble");
    if (!bubble) return;

    // Get text content, stripping HTML
    let text = bubble.innerText || bubble.textContent;
    text = text.trim();

    if (!text) return;

    const sender = isUser ? "YOU" : "INVOICEBOT";

    output += `[${sender}]\n`;
    output += `${text}\n`;
    output += "\n───────────────────────────────────────────────────────────\n\n";
  });

  output += "═══════════════════════════════════════════════════════════\n";
  output += "                     END OF TRANSCRIPT\n";
  output += "═══════════════════════════════════════════════════════════\n";

  // Create and download file
  const blob = new Blob([output], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");

  // Generate filename with date
  const filename = `InvoiceBot_Chat_${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}.txt`;

  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  console.log("📥 Conversation downloaded:", filename);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

let chatbot;

document.addEventListener("DOMContentLoaded", () => {
  // Only initialize if chatbot elements exist on page
  if (document.getElementById("chat-window")) {
    chatbot = new InvoiceChatbot();
    console.log("✅ Chatbot ready");
  }
});
