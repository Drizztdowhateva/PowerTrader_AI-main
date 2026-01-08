"""
Exchange Credential Manager

A flexible, extensible framework for managing API credentials across multiple exchanges.
This module provides:
1. CredentialManager - Generic credential storage/retrieval for any exchange
2. ExchangeConfig - Configuration template for adding new exchanges
3. Helper functions for wizard generation and credential management

Usage:
    # Define configuration for a new exchange
    new_exchange_config = ExchangeConfig(
        name="myexchange",
        display_name="My Exchange",
        credential_fields=["api_key", "api_secret"],
        api_endpoints={"market_data": "https://api.myexchange.com/v1/klines"},
        auth_method="hmac-sha256"
    )
    
    # Get/set credentials
    manager = CredentialManager(new_exchange_config)
    key, secret = manager.read_credentials()
    manager.write_credentials(key, secret)
"""

import os
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExchangeConfig:
    """Configuration template for a new exchange API"""
    
    # Basic identifiers
    name: str  # Lowercase identifier (e.g., "binance", "kraken")
    display_name: str  # User-friendly name (e.g., "Binance", "Kraken")
    
    # Credential fields this exchange requires
    credential_fields: List[str]  # e.g., ["api_key", "api_secret"]
    
    # API endpoints for reference
    api_endpoints: Dict[str, str] = field(default_factory=dict)  
    # e.g., {"market_data": "https://...", "trading": "https://..."}
    
    # Authentication method
    auth_method: str = "unknown"  # e.g., "hmac-sha256", "ed25519", "rsa"
    
    # File extension (default: .txt)
    file_extension: str = "txt"
    
    # Base directory for credentials (default: current directory)
    base_dir: str = "."
    
    # Whether credentials are base64-encoded
    base64_encoded_fields: List[str] = field(default_factory=list)
    
    # Setup instructions shown to users
    setup_instructions: Dict[str, str] = field(default_factory=dict)
    # e.g., {"api_key": "Get from https://...", "api_secret": "Shown once"}
    
    # Feature flags
    supports_market_data: bool = True
    supports_trading: bool = True
    supports_margin_trading: bool = False
    supports_futures: bool = False


class CredentialManager:
    """Manage credentials for a single exchange with file I/O and validation"""
    
    def __init__(self, config: ExchangeConfig):
        """Initialize credential manager for an exchange
        
        Args:
            config: ExchangeConfig instance for the exchange
        """
        self.config = config
        self.base_path = Path(config.base_dir)
        
    def _get_file_path(self, field_name: str) -> Path:
        """Get the file path for a credential field
        
        Args:
            field_name: Name of the credential field (e.g., "api_key")
            
        Returns:
            Path object for the credential file
        """
        filename = f"{self.config.name}_{field_name}.{self.config.file_extension}"
        return self.base_path / filename
    
    def write_credentials(self, credentials: Dict[str, str]) -> Tuple[bool, str]:
        """Write credentials to files
        
        Args:
            credentials: Dict mapping field names to credential values
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            for field_name, value in credentials.items():
                if field_name not in self.config.credential_fields:
                    return False, f"Unknown credential field: {field_name}"
                
                if not value or not value.strip():
                    return False, f"Credential '{field_name}' cannot be empty"
                
                file_path = self._get_file_path(field_name)
                file_path.write_text(value.strip())
            
            return True, "Credentials saved successfully"
        
        except Exception as e:
            return False, f"Error saving credentials: {str(e)}"
    
    def read_credentials(self) -> Tuple[Dict[str, str], bool]:
        """Read credentials from files
        
        Args:
            None
            
        Returns:
            Tuple of (credentials_dict, success: bool)
            Returns empty dict if files don't exist or can't be read
        """
        credentials = {}
        
        try:
            for field_name in self.config.credential_fields:
                file_path = self._get_file_path(field_name)
                
                if file_path.exists():
                    value = file_path.read_text().strip()
                    if value:
                        credentials[field_name] = value
            
            success = len(credentials) == len(self.config.credential_fields)
            return credentials, success
        
        except Exception as e:
            print(f"Error reading credentials: {e}")
            return {}, False
    
    def credentials_exist(self) -> bool:
        """Check if all credential files exist with non-empty content
        
        Returns:
            True if all required credentials exist and are non-empty
        """
        for field_name in self.config.credential_fields:
            file_path = self._get_file_path(field_name)
            
            if not file_path.exists():
                return False
            
            content = file_path.read_text().strip()
            if not content or content.startswith("PLACEHOLDER"):
                return False
        
        return True
    
    def delete_credentials(self) -> Tuple[bool, str]:
        """Delete all credential files for this exchange
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            deleted = 0
            for field_name in self.config.credential_fields:
                file_path = self._get_file_path(field_name)
                if file_path.exists():
                    file_path.unlink()
                    deleted += 1
            
            return True, f"Deleted {deleted} credential files"
        
        except Exception as e:
            return False, f"Error deleting credentials: {str(e)}"
    
    def get_file_paths(self) -> Dict[str, str]:
        """Get file paths for all credential fields
        
        Returns:
            Dict mapping field names to file paths
        """
        return {
            field: str(self._get_file_path(field))
            for field in self.config.credential_fields
        }


class ExchangeRegistry:
    """Central registry for all configured exchanges"""
    
    def __init__(self):
        self.exchanges: Dict[str, ExchangeConfig] = {}
    
    def register(self, config: ExchangeConfig) -> None:
        """Register an exchange configuration
        
        Args:
            config: ExchangeConfig instance
        """
        self.exchanges[config.name] = config
    
    def get(self, name: str) -> Optional[ExchangeConfig]:
        """Get an exchange configuration by name
        
        Args:
            name: Exchange name (lowercase)
            
        Returns:
            ExchangeConfig or None if not found
        """
        return self.exchanges.get(name)
    
    def list_all(self) -> Dict[str, ExchangeConfig]:
        """Get all registered exchanges
        
        Returns:
            Dict of all exchanges
        """
        return self.exchanges.copy()
    
    def list_names(self) -> List[str]:
        """Get names of all registered exchanges
        
        Returns:
            List of exchange names
        """
        return list(self.exchanges.keys())


# Global registry instance
_global_registry = ExchangeRegistry()


def register_exchange(config: ExchangeConfig) -> None:
    """Register an exchange globally
    
    Args:
        config: ExchangeConfig instance
    """
    _global_registry.register(config)


def get_exchange_config(name: str) -> Optional[ExchangeConfig]:
    """Get an exchange configuration by name
    
    Args:
        name: Exchange name (lowercase)
        
    Returns:
        ExchangeConfig or None if not found
    """
    return _global_registry.get(name)


def list_exchanges() -> List[str]:
    """Get list of all registered exchanges
    
    Returns:
        List of exchange names
    """
    return _global_registry.list_names()


def create_wizard_template(exchange_name: str) -> Dict[str, Any]:
    """Generate a template for creating a setup wizard for an exchange
    
    This template shows the structure needed for a setup wizard in pt_hub.py
    
    Args:
        exchange_name: Name of the exchange
        
    Returns:
        Dict with wizard template structure
    """
    config = get_exchange_config(exchange_name)
    if not config:
        return {}
    
    manager = CredentialManager(config)
    
    return {
        "exchange_name": config.name,
        "display_name": config.display_name,
        "credential_fields": config.credential_fields,
        "file_paths": manager.get_file_paths(),
        "setup_instructions": config.setup_instructions,
        "auth_method": config.auth_method,
        "features": {
            "market_data": config.supports_market_data,
            "trading": config.supports_trading,
            "margin": config.supports_margin_trading,
            "futures": config.supports_futures,
        }
    }


if __name__ == "__main__":
    # Example: Register and use an exchange
    example_exchange = ExchangeConfig(
        name="example",
        display_name="Example Exchange",
        credential_fields=["api_key", "api_secret"],
        api_endpoints={
            "market_data": "https://api.example.com/v1/klines",
            "trading": "https://api.example.com/v1/orders"
        },
        auth_method="hmac-sha256",
        setup_instructions={
            "api_key": "Get from https://example.com/api/management",
            "api_secret": "Shown only once during creation"
        }
    )
    
    register_exchange(example_exchange)
    
    # Test credential manager
    manager = CredentialManager(example_exchange)
    print(f"Exchange: {example_exchange.display_name}")
    print(f"Credential fields: {example_exchange.credential_fields}")
    print(f"File paths: {manager.get_file_paths()}")
    print(f"Credentials exist: {manager.credentials_exist()}")
