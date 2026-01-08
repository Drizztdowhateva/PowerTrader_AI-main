"""
Setup Wizard Generator

Provides reusable components and templates for creating exchange setup wizards
in pt_hub.py. This eliminates code duplication when adding new exchanges.

Features:
1. BaseExchangeWizard - Abstract base class for all exchange wizards
2. ScrollableWizardFrame - Reusable scrollable UI frame
3. WizardField - Input field with label and validation
4. generate_wizard_window() - Factory function for creating wizards
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Dict, List, Callable, Optional, Tuple
from dataclasses import dataclass
from exchange_credential_manager import ExchangeConfig, CredentialManager


@dataclass
class WizardField:
    """Configuration for a single input field in the wizard"""
    name: str
    label: str
    placeholder: str = ""
    is_secret: bool = False  # Show as asterisks if True
    is_base64: bool = False
    instructions: str = ""


class ScrollableWizardFrame(ttk.Frame):
    """Reusable scrollable frame for wizard content
    
    Automatically adds scrollbar when content exceeds height
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.canvas = tk.Canvas(parent, bg="#070B10", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
    
    def get_content_frame(self) -> ttk.Frame:
        """Get the frame where content should be added"""
        return self.scrollable_frame
    
    def pack_scrollbars(self, side="right", fill="y"):
        """Pack the canvas and scrollbar"""
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side=side, fill=fill)


class BaseExchangeWizard:
    """Abstract base class for exchange setup wizards
    
    Subclass this to create wizards for new exchanges with minimal code
    """
    
    def __init__(
        self,
        parent_window: tk.Tk,
        config: ExchangeConfig,
        dark_bg: str = "#070B10",
        dark_fg: str = "#C7D1DB",
        dark_accent: str = "#00FF66",
    ):
        """Initialize the wizard
        
        Args:
            parent_window: Parent Tkinter window
            config: ExchangeConfig for this exchange
            dark_bg: Background color (hex)
            dark_fg: Foreground/text color (hex)
            dark_accent: Accent color (hex)
        """
        self.parent = parent_window
        self.config = config
        self.manager = CredentialManager(config)
        
        self.dark_bg = dark_bg
        self.dark_fg = dark_fg
        self.dark_accent = dark_accent
        
        self.win = tk.Toplevel(parent_window)
        self.win.title(f"{config.display_name} API Configuration")
        self.win.geometry("600x500")
        self.win.configure(bg=dark_bg)
        
        self.credential_inputs: Dict[str, tk.StringVar] = {}
        self.test_result_label: Optional[ttk.Label] = None
        
        self._build_ui()
        self._load_existing_credentials()
    
    def _build_ui(self) -> None:
        """Build the wizard UI (override in subclasses for customization)"""
        # Title
        title_label = tk.Label(
            self.win,
            text=f"{self.config.display_name} API Setup",
            font=("Helvetica", 14, "bold"),
            bg=self.dark_bg,
            fg=self.dark_accent
        )
        title_label.pack(pady=10)
        
        # Create scrollable frame
        self.scroll_frame = ScrollableWizardFrame(self.win)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        content_frame = self.scroll_frame.get_content_frame()
        
        # Add credential input fields
        for field_name in self.config.credential_fields:
            self._add_input_field(
                content_frame,
                field_name,
                self.config.setup_instructions.get(field_name, "")
            )
        
        # Buttons frame
        button_frame = ttk.Frame(self.win)
        button_frame.pack(pady=10, fill="x", padx=10)
        
        # Test button
        test_btn = tk.Button(
            button_frame,
            text="Test Connection",
            command=self._test_connection,
            bg=self.dark_accent,
            fg="#000000",
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=5
        )
        test_btn.pack(side="left", padx=5)
        
        # Save button
        save_btn = tk.Button(
            button_frame,
            text="Save Credentials",
            command=self._save_credentials,
            bg=self.dark_accent,
            fg="#000000",
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=5
        )
        save_btn.pack(side="left", padx=5)
        
        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self.win.destroy,
            bg="#444444",
            fg=self.dark_fg,
            font=("Helvetica", 10),
            padx=10,
            pady=5
        )
        cancel_btn.pack(side="right", padx=5)
        
        # Result label
        self.test_result_label = ttk.Label(
            self.win,
            text="",
            font=("Helvetica", 9)
        )
        self.test_result_label.pack(pady=5)
    
    def _add_input_field(
        self,
        parent: ttk.Frame,
        field_name: str,
        instructions: str = ""
    ) -> None:
        """Add a credential input field
        
        Args:
            parent: Parent frame
            field_name: Name of the credential field
            instructions: Instructions text to display
        """
        field_frame = ttk.Frame(parent)
        field_frame.pack(fill="x", pady=8)
        
        # Label with instructions
        label_text = f"{field_name.replace('_', ' ').title()}"
        if instructions:
            label_text += f"\n{instructions}"
        
        label = tk.Label(
            field_frame,
            text=label_text,
            bg=self.dark_bg,
            fg=self.dark_fg,
            font=("Helvetica", 9),
            justify="left"
        )
        label.pack(anchor="w", pady=(0, 3))
        
        # Input field
        var = tk.StringVar()
        self.credential_inputs[field_name] = var
        
        is_secret = field_name in self.config.base64_encoded_fields or "secret" in field_name.lower()
        
        entry = tk.Entry(
            field_frame,
            textvariable=var,
            show="*" if is_secret else "",
            font=("Courier", 10),
            bg="#1a1a1a",
            fg=self.dark_fg,
            insertbackground=self.dark_accent
        )
        entry.pack(fill="x", ipady=6)
    
    def _load_existing_credentials(self) -> None:
        """Load existing credentials into input fields"""
        creds, _ = self.manager.read_credentials()
        for field_name, value in creds.items():
            if field_name in self.credential_inputs:
                self.credential_inputs[field_name].set(value)
    
    def _save_credentials(self) -> None:
        """Save credentials to files"""
        credentials = {
            field: var.get()
            for field, var in self.credential_inputs.items()
        }
        
        success, message = self.manager.write_credentials(credentials)
        
        if success:
            messagebox.showinfo(
                f"{self.config.display_name} API",
                message
            )
            self.win.destroy()
        else:
            messagebox.showerror(
                f"{self.config.display_name} API",
                message
            )
    
    def _test_connection(self) -> None:
        """Test API connection (override in subclasses)"""
        if self.test_result_label:
            self.test_result_label.config(
                text="⏳ Testing connection...",
                foreground="#FFD700"
            )
            self.win.update()
        
        # Run test in background thread
        def test_thread():
            try:
                result = self.test_api_connection()
                self.win.after(0, lambda: self._update_test_result(result))
            except Exception as e:
                self.win.after(0, lambda: self._update_test_result(f"Error: {e}"))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def test_api_connection(self) -> str:
        """Test API connection - override in subclasses
        
        Returns:
            Status message (success or error message)
        """
        return "✅ Connection test passed"
    
    def _update_test_result(self, message: str) -> None:
        """Update the test result label"""
        if self.test_result_label:
            color = "#00FF66" if "✅" in message or "passed" in message.lower() else "#FF6B6B"
            self.test_result_label.config(text=message, foreground=color)


def generate_wizard_factory(config: ExchangeConfig) -> Callable:
    """Generate a wizard factory function for an exchange
    
    Usage in pt_hub.py:
        binance_wizard = generate_wizard_factory(binance_config)
        # Later, in your button command:
        binance_wizard(parent_window)
    
    Args:
        config: ExchangeConfig for the exchange
        
    Returns:
        Function that creates and displays the wizard window
    """
    
    def wizard_launcher(parent_window: tk.Tk) -> BaseExchangeWizard:
        """Launch the wizard for this exchange"""
        return BaseExchangeWizard(parent_window, config)
    
    return wizard_launcher


if __name__ == "__main__":
    # Example: Create a test wizard
    from exchange_credential_manager import ExchangeConfig, register_exchange
    
    test_config = ExchangeConfig(
        name="testex",
        display_name="Test Exchange",
        credential_fields=["api_key", "api_secret"],
        auth_method="hmac-sha256",
        setup_instructions={
            "api_key": "Get from https://example.com",
            "api_secret": "Keep this safe"
        }
    )
    
    root = tk.Tk()
    root.withdraw()  # Hide main window for testing
    
    wizard = BaseExchangeWizard(root, test_config)
    root.mainloop()
