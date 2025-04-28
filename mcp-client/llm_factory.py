from typing import Optional, Any
import logging
from config import LLMConfig

logger = logging.getLogger(__name__)

def create_llm_client(config: LLMConfig) -> Optional[Any]:
    """Create LLM client instance based on provider configuration"""
    if not config.api_key:
        logger.warning(f"Missing {config.provider} API key, cannot initialize LLM client")
        return None
        
    try:
        if config.provider == "zhipuai":
            from zhipuai import ZhipuAI
            return ZhipuAI(api_key=config.api_key)
            
        elif config.provider == "deepseek":
            from openai import OpenAI
            return OpenAI(
                api_key=config.api_key,
                base_url=config.base_url or "https://api.deepseek.com/v1"
            )
            
        elif config.provider == "openai_compatible":
            from openai import OpenAI
            if not config.base_url:
                logger.error("base_url is required for openai_compatible provider")
                return None
                
            return OpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )
            
        else:
            logger.error(f"Unsupported LLM provider: {config.provider}")
            return None
            
    except ImportError as e:
        logger.error(f"Cannot import module required for {config.provider}: {e}")
        if config.provider == "zhipuai":
            logger.error("Please install zhipuai: pip install zhipuai")
        elif config.provider in ["deepseek", "openai_compatible"]:
            logger.error("Please install openai: pip install openai")
        return None
        
    except Exception as e:
        logger.error(f"Error initializing {config.provider} client: {e}", exc_info=True)
        return None 
