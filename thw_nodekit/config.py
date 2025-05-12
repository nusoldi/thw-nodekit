"""Unified configuration system for THW-NodeKit."""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Handle different Python versions for TOML support
if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli
import tomli_w


class Config:
    """Unified configuration manager for all NodeKit components."""
    
    def __init__(self, custom_config_path: Optional[str] = None):
        """Initialize configuration with unified loading strategy.
        
        Args:
            custom_config_path: Path to a custom config file (highest priority)
        """
        self.config_data = {}
        
        # Define config file paths in order of priority
        self.config_paths = self._get_config_paths(custom_config_path)
        
        # Load configuration, starting with defaults and overriding
        self._load_configuration()
    
    def _get_config_paths(self, custom_path: Optional[str] = None) -> List[Path]:
        """Get configuration file paths in priority order.
        
        Args:
            custom_path: Optional custom config path
            
        Returns:
            List of config paths in priority order (highest priority first)
        """
        paths = []
        
        # 1. Custom path (if provided) - highest priority
        if custom_path:
            paths.append(Path(custom_path))
        
        # 2. Project root local config (for development)
        project_root = Path(__file__).parent.parent
        paths.append(project_root / "config.local.toml")
        
        # 3. User config in ~/.config (for user customization)
        paths.append(Path.home() / ".config" / "nusoldi" / "config.toml")
        
        # 4. Project default config (for baseline values)
        paths.append(project_root / "config.default.toml")
        
        # 5. Package default configs (fallbacks)
        buildkit_default = project_root / "thw_buildkit" / "config" / "default.toml"
        
        if buildkit_default.exists():
            paths.append(buildkit_default)
        
        return paths
    
    def _load_configuration(self):
        """Load configuration from all paths, with priority override."""
        # Start with an empty config
        config = {}
        
        # Reverse the paths list to load from lowest to highest priority
        for path in reversed(self.config_paths):
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        new_config = tomli.load(f)
                        # Deep merge with existing config
                        self._deep_merge(config, new_config)
                except Exception as e:
                    print(f"Warning: Error reading config file {path}: {e}")
        
        # Store the merged config
        self.config_data = config
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.
        
        Args:
            key: The key to retrieve, can use dot notation for nested keys
            default: Default value if key doesn't exist
            
        Returns:
            The configuration value or default
        """
        keys = key.split('.')
        result = self.config_data
        
        for k in keys:
            if isinstance(result, dict) and k in result:
                result = result[k]
            else:
                return default
                
        return result
    
    def set(self, key: str, value: Any, save_path: Optional[Path] = None) -> bool:
        """Set a configuration value and optionally save to file.
        
        Args:
            key: The key to set, can use dot notation for nested keys
            value: The value to set
            save_path: Path to save updated config (default: first writable path)
            
        Returns:
            True if successful, False otherwise
        """
        keys = key.split('.')
        config = self.config_data
        
        # Navigate to the nested dict where the value should be set
        for i, k in enumerate(keys[:-1]):
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save to file if requested
        if save_path:
            return self.save(save_path)
            
        return True
    
    def save(self, path: Optional[Union[str, Path]] = None) -> bool:
        """Save the current configuration to a file.
        
        Args:
            path: Path to save the config (default: first writable path)
            
        Returns:
            True if successful, False otherwise
        """
        # Determine the path to save to
        save_path = Path(path) if path else self.config_paths[0]
        
        try:
            # Create parent directory if it doesn't exist
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the config
            with open(save_path, "wb") as f:
                tomli_w.dump(self.config_data, f)
            return True
        except Exception as e:
            print(f"Error saving configuration to {save_path}: {e}")
            return False
    
    # Additional helper methods for buildkit
    
    def get_repo_url(self, client: str, repo_type: str) -> str:
        """Get repository URL for the specified client and type."""
        key = f"{client}_{repo_type}"
        return self.config_data.get("repositories", {}).get(key, "")
    
    def get_install_dir(self, client: str, tag: str) -> str:
        """Get installation directory for the specified client and tag."""
        base = self.config_data.get("paths", {}).get("install_dir", "")
        return os.path.join(base, client, tag)
    
    def get_source_dir(self, client: str, tag: str) -> str:
        """Get source directory for the specified client and tag.

        Firedancer builds directly in its installation directory.
        Other projects (Agave, Jito) clone to a separate source directory.
        """
        if client == "firedancer":
            # Firedancer clones and builds directly in the installation directory
            return self.get_install_dir(client, tag)
        else:
            # Agave/Jito clone to a separate source directory structure
            base = self.config_data.get("paths", {}).get("source_dir", "")
            if not base:
                raise ValueError("Configuration missing: paths.source_dir")
            return os.path.join(base, client, tag)
    
    def get_symlink_target(self, client: str, tag: str) -> str:
        """Get symlink target path for the specified client and tag."""
        install_dir = self.get_install_dir(client, tag)
        
        if client == "firedancer":
            subpath = self.config_data.get("paths", {}).get("firedancer", {}).get("symlink_subpath", "")
            return os.path.join(install_dir, subpath)
        
        return install_dir
    
    def get_symlink_path(self) -> str:
        """Get symlink path."""
        return self.config_data.get("paths", {}).get("symlink_path", "")
    
    def get_build_jobs(self) -> int:
        """Get number of parallel jobs for building."""
        return self.config_data.get("build", {}).get("parallel_jobs", 4)


# Global configuration instance
_config_instance = None

def get_config(custom_path=None):
    """Get the config instance, creating it if necessary."""
    global _config_instance
    if _config_instance is None or custom_path:
        _config_instance = Config(custom_path)
    return _config_instance

def update_config(key, value, save=False):
    """Update a configuration value."""
    config = get_config()
    result = config.set(key, value)
    
    if save:
        config.save()
        
    return result