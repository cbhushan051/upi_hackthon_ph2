"""
LLM module using LangChain's ChatOpenAI.
"""

import os
import warnings
from typing import Optional, List

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    warnings.warn("langchain packages not available. LLM features will be limited.")


class LLM:
    """LLM wrapper class using LangChain's ChatOpenAI."""
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the LLM using ChatOpenAI.
        
        Args:
            model: Model name/identifier (e.g., 'gpt-3.5-turbo', 'gpt-4')
            api_key: OpenAI API key (if not provided, uses OPENAI_API_KEY env var)
            base_url: Base URL for the API endpoint (useful for OpenAI-compatible APIs or local models)
        """
        self.model = model or os.environ.get("LLM_MODEL", "NPCI_Greviance")
        # Get API key from parameter, env vars, or dummy key for local model
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "sk-xxx"
        self.base_url = base_url or os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "http://183.82.7.228:9532/v1"
        self._chat_model = None
        self._use_llm = bool(self.api_key) and LANGCHAIN_AVAILABLE
        
        if not self._use_llm:
            if not LANGCHAIN_AVAILABLE:
                warnings.warn("LangChain not available. Using fallback mode without LLM.")
            elif not self.api_key:
                warnings.warn("No API key provided. Using fallback mode without LLM. Set OPENAI_API_KEY environment variable to enable LLM features.")
    
    def _get_chat_model(self):
        """Lazy initialization of ChatOpenAI model."""
        if self._chat_model is None:
            if not self._use_llm:
                raise RuntimeError(
                    "LLM not available. Please set OPENAI_API_KEY environment variable "
                    "or provide api_key parameter to enable LLM features."
                )
            
            # Initialize ChatOpenAI
            chat_model_kwargs = {
                "model_name": self.model,
                "temperature": 0.2,
                "max_tokens": 2048,
                "streaming": False,
            }
            
            # Add API key (required for ChatOpenAI)
            if self.api_key:
                chat_model_kwargs["openai_api_key"] = self.api_key
            else:
                # If no API key provided, ChatOpenAI will try to use OPENAI_API_KEY env var
                # If that's also not set, it will raise an error which we'll catch
                pass
            
            # Add base_url if provided
            if self.base_url:
                chat_model_kwargs["base_url"] = self.base_url
            
            try:
                self._chat_model = ChatOpenAI(**chat_model_kwargs)
            except Exception as e:
                error_msg = str(e)
                if "api_key" in error_msg.lower() or "api key" in error_msg.lower():
                    warnings.warn(
                        f"API key required but not provided: {error_msg}. "
                        "Using fallback mode. Set OPENAI_API_KEY environment variable to enable LLM."
                    )
                else:
                    warnings.warn(f"Failed to initialize ChatOpenAI: {e}. Using fallback mode.")
                self._use_llm = False
                raise RuntimeError(f"LLM initialization failed: {error_msg}")
        
        return self._chat_model
    
    def _convert_messages(self, messages: List[dict]) -> List[BaseMessage]:
        """
        Convert list of dict messages to LangChain BaseMessage objects.
        
        Args:
            messages: List of dicts with 'role' and 'content' keys
            
        Returns:
            List of LangChain BaseMessage objects
        """
        if not LANGCHAIN_AVAILABLE:
            return []
        
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            
            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif role == "system":
                langchain_messages.append(SystemMessage(content=content))
            else:
                # Default to human message if role is unknown
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: Input prompt for the LLM
            **kwargs: Additional parameters for generation
            
        Returns:
            Generated text response
        """
        if not self._use_llm:
            # Fallback: return a simple response indicating LLM is not available
            return f"[LLM Fallback Mode] Processing request: {prompt[:100]}..."
        
        try:
            messages = [HumanMessage(content=prompt)]
            chat_model = self._get_chat_model()
            response = chat_model.invoke(messages, **kwargs)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            warnings.warn(f"LLM generation failed: {e}. Using fallback response.")
            return f"[LLM Error] {str(e)}. Request: {prompt[:100]}..."
    
    def chat(self, messages: List[dict], **kwargs) -> str:
        """
        Chat with the LLM using a list of messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters for generation
            
        Returns:
            Generated text response
        """
        if not messages:
            return "[No messages provided]"
        
        if not self._use_llm:
            # Fallback: extract last user message
            last_message = messages[-1].get("content", "") if messages else ""
            return f"[LLM Fallback Mode] Processing: {last_message[:100]}..."
        
        try:
            # Convert messages to LangChain format
            langchain_messages = self._convert_messages(messages)
            
            # Invoke the chat model
            chat_model = self._get_chat_model()
            response = chat_model.invoke(langchain_messages, **kwargs)
            
            # Extract content from response
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            warnings.warn(f"LLM chat failed: {e}. Using fallback response.")
            last_message = messages[-1].get("content", "") if messages else ""
            return f"[LLM Error] {str(e)}. Last message: {last_message[:100]}..."


# Create a default instance (will use fallback mode if no API key is set)
# Users should set OPENAI_API_KEY environment variable or pass api_key explicitly
# The LLM class handles missing API keys gracefully by using fallback mode
llm = LLM()
