"""
New Invoice Chatbot Module
Hybrid chatbot with improved disambiguation and SQL generation
"""
# Legacy v1 chatbot (for backwards compatibility)
from .chatbot import chatbot, InvoiceChatbot

# New v2 chatbot (consolidated prompts, faster)
from .chatbot_v2 import chatbot_v2, InvoiceChatbotV2

__all__ = ['chatbot', 'InvoiceChatbot', 'chatbot_v2', 'InvoiceChatbotV2']

