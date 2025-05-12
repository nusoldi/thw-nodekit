"""Initialization display."""

import time
import atexit
from typing import Dict, Any, Optional, Tuple

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich.box import ROUNDED, DOUBLE_EDGE
from rich.spinner import Spinner
from rich.progress import ProgressBar

from thw_nodekit import __version__

from .constants import (
    STYLE_CYAN, STYLE_BRIGHT_CYAN, STYLE_GREEN, STYLE_GREEN_BOLD, STYLE_RED,
    STYLE_BOLD_RED, STYLE_DIM, STYLE_YELLOW_BOLD, STYLE_CYAN_BOLD,
    STYLE_BLUE_BOLD, STYLE_MAGENTA_BOLD, PADDING_NONE, PADDING_STANDARD,
    ICON_SUCCESS, ICON_FAILED, ICON_RETRYING, ICON_CRITICAL, ICON_WAITING,
    APP_NAME, HEADER_TITLE_TVC
)

# Default status data keys
DEFAULT_STATUS_DATA = [
    "vote_accounts",
    "cluster_nodes",
    "validator_info", 
    "epoch_info",
    "leader_schedule",
    "block_production",
    "validator_data",
    "SUMMARY"
]

class StartupDisplay:
    """Display component for showing initialization progress in the terminal.
    
    This class handles the rich-based display for application startup,
    including status updates for each initialization step.
    """
    
    def __init__(self) -> None:
        """Initialize Rich display components and register cleanup handler."""
        self.console = Console()
        self.live: Optional[Live] = None
        self.status_data: Dict[str, Dict[str, str]] = {}
        
        # Register cleanup handler
        atexit.register(self.cleanup)
    
    def cleanup(self) -> None:
        """Ensure terminal state is restored properly on exit."""
        if self.live:
            try:
                # Stop the live display
                self.live.stop()
                # Explicitly show cursor
                print("\033[?25h", end="", flush=True)
            except Exception:
                # Fallback if normal cleanup fails
                print("\033[?25h", end="", flush=True)
    
    def _create_styled_panel(
        self, 
        content: Any, 
        title: str, 
        title_align: str = "left", 
        border_style: str = STYLE_BRIGHT_CYAN, 
        padding: Tuple[int, int] = PADDING_STANDARD
    ) -> Panel:
        """Create a styled panel with consistent formatting.
        
        Args:
            content: Content to place in the panel
            title: Panel title
            title_align: Alignment of the title
            border_style: Color/style of the panel border
            padding: Padding inside the panel
            
        Returns:
            Rich Panel object
        """
        return Panel(
            content,
            title=Text(title, style=STYLE_GREEN_BOLD),
            title_align=title_align,
            border_style=border_style,
            padding=padding
        )
    
    def _create_logo(self) -> Text:
        """Create the THW styled logo.
        
        Returns:
            Rich Text object containing the logo
        """
        styled_logo = Text()
        styled_logo.append("████████╗", style=STYLE_CYAN_BOLD)
        styled_logo.append("██╗  ██╗", style=STYLE_BLUE_BOLD)
        styled_logo.append("██╗    ██╗", style=STYLE_MAGENTA_BOLD)
        styled_logo.append("\n╚══██╔══╝", style=STYLE_CYAN_BOLD)
        styled_logo.append("██║  ██║", style=STYLE_BLUE_BOLD)
        styled_logo.append("██║    ██║", style=STYLE_MAGENTA_BOLD)
        styled_logo.append("\n   ██║   ", style=STYLE_CYAN_BOLD)
        styled_logo.append("███████║", style=STYLE_BLUE_BOLD)
        styled_logo.append("██║ █╗ ██║", style=STYLE_MAGENTA_BOLD)
        styled_logo.append("\n   ██║   ", style=STYLE_CYAN_BOLD)
        styled_logo.append("██╔══██║", style=STYLE_BLUE_BOLD)
        styled_logo.append("╚███╔███╔╝", style=STYLE_MAGENTA_BOLD)
        styled_logo.append("\n   ╚═╝   ", style=STYLE_CYAN_BOLD)
        styled_logo.append("╚═╝  ╚═╝", style=STYLE_BLUE_BOLD)
        styled_logo.append(" ╚══╝╚══╝", style=STYLE_MAGENTA_BOLD)
        return styled_logo
    
    
    def _calculate_progress(self) -> float:
        """Calculate the current progress percentage based on successful status checks.
        
        Returns:
            Progress percentage (0.0 to 1.0)
        """
        if not self.status_data:
            return 0.0
        
        # Don't count SUMMARY in the calculation
        total_items = len(self.status_data) - 1 if "SUMMARY" in self.status_data else len(self.status_data)
        if total_items <= 0:
            return 0.0
        
        # Count successful items
        successful_items = 0
        for key, data in self.status_data.items():
            if key != "SUMMARY" and data.get("status") == ICON_SUCCESS:
                successful_items += 1
        
        return successful_items / total_items
    
    def _create_progress_bar(self, width: int = 20) -> Text:
        """Create a text-based progress bar based on the current status.
        
        Args:
            width: Width of the progress bar in characters
            
        Returns:
            Rich Text object containing the progress bar
        """
        progress = self._calculate_progress()
        filled_width = int(progress * width)
        empty_width = width - filled_width
        
        # Create the progress bar
        progress_text = Text()
        
        # Add the filled part
        if filled_width > 0:
            progress_text.append("█" * filled_width, style=STYLE_GREEN_BOLD)
        
        # Add the empty part
        if empty_width > 0:
            progress_text.append("░" * empty_width, style=STYLE_DIM)
        
        # Add percentage
        percentage = int(progress * 100)
        progress_text.append(f" {percentage}%", style=STYLE_BRIGHT_CYAN)
        
        return progress_text
    
    def create_header_content(self, title: str = HEADER_TITLE_TVC) -> Align:
        """Create the header content with logo and title.
        
        Args:
            title: The title to display in the header
            
        Returns:
            Aligned content for the header
        """
        styled_logo = self._create_logo()
        
        # Create progress bar
        progress_bar = self._create_progress_bar(width=8)
        
        # Header text content
        header_text = Text()
        header_text.append(f"{APP_NAME}\n", style=STYLE_GREEN_BOLD)
        header_text.append(f"{title}\n", style=STYLE_BRIGHT_CYAN)
        header_text.append(f"v{__version__}\n", style=STYLE_DIM)
        header_text.append("INITIALIZING\n", style=STYLE_YELLOW_BOLD)
        header_text.append(progress_bar)
        header_text.append("\n")
        
        # Check console width to determine layout approach
        console_width = self.console.width
        
        if console_width < 80:
            # For narrow terminals, stack logo and text vertically
            content = Group(
                Align.center(header_text),
                Align.center(styled_logo)
            )
            return Align.center(content)
        else:
            # For wider terminals, use a table for more stable side-by-side layout
            layout_table = Table.grid(padding=(0, 2))
            layout_table.add_column(justify="right", ratio=1)
            layout_table.add_column(justify="left", ratio=1)
            layout_table.add_row(header_text, styled_logo)
            
            return Align.center(layout_table)
    
    def create_startup_logo(self, title: str) -> Panel:
        """Create a standardized header panel for Rich display.
        
        Args:
            title: The title to display in the header
            
        Returns:
            Panel containing the header
        """
        header_content = self.create_header_content(title)
        return Panel(
            header_content, 
            border_style=STYLE_GREEN_BOLD, 
            box=DOUBLE_EDGE, 
            padding=PADDING_NONE
        )
    
    def start_initialization(self) -> None:
        """Start the initialization display with a status table."""
        # Create a status dictionary to store initialization status
        self.status_data = {
            key: {"status": ICON_WAITING, "details": "", "style": STYLE_DIM}
            for key in DEFAULT_STATUS_DATA
        }
        # Set summary message
        self.status_data["SUMMARY"]["details"] = "Initialization in progress..."
        
        # Render the initial display
        self._render_display()
    
    def _render_display(self) -> None:
        """Render the current state of the display."""
        # Create a fixed-width status table
        table_width = 80  # Fixed width for the entire table
        status_table = Table(
            show_header=True, 
            box=ROUNDED, 
            width=table_width,
            expand=False,
            padding=(0, 1),
            border_style=STYLE_BRIGHT_CYAN
        )
        
        # Add fixed-width columns
        status_table.add_column("Data Type", style=STYLE_BRIGHT_CYAN, justify="center", width=3)
        status_table.add_column("Status", style=STYLE_BRIGHT_CYAN, justify="center", width=2)
        status_table.add_column("Details", style=STYLE_BRIGHT_CYAN, justify="center", width=5)
        
        # Add rows for each data type
        for data_type, data in self.status_data.items():
            status_text = Text(data["status"], style=data["style"])
            details_text = Text(data["details"], style=data["style"])
            status_table.add_row(Text(data_type), status_text, details_text)
        
        # Create the header with logo and banner
        header_content = self.create_header_content()
        
        # Create a footer text with quit instructions
        footer_text = Text("Press Ctrl+C to cancel at any time", style=STYLE_YELLOW_BOLD)
        
        # Group the elements together
        main_content = Group(
            header_content,
            Align.center(status_table),
            Align.center(footer_text)
        )
        
        # Create a panel for the content
        main_panel = Panel(
            main_content,
            border_style=STYLE_GREEN_BOLD,
            box=DOUBLE_EDGE,
            padding=PADDING_NONE
        )
        
        # Create or update the live display
        if self.live is None:
            self.live = Live(main_panel, console=self.console, refresh_per_second=20, screen=True)
            self.live.start()
        else:
            self.live.update(main_panel)
    
    def update_initialization_status(self, data_type: str, success: bool, error_msg: Optional[str] = None) -> None:
        """Update the status of a data type during initialization.
        
        Args:
            data_type: The key of the data to update
            success: Whether the initialization step succeeded
            error_msg: Optional error message to display if failed
        """
        if data_type not in self.status_data:
            return
            
        if success:
            self.status_data[data_type] = {
                "status": ICON_SUCCESS,
                "details": "Data loaded successfully",
                "style": STYLE_GREEN_BOLD
            }
        else:
            self.status_data[data_type] = {
                "status": ICON_FAILED,
                "details": error_msg or "Failed to load data",
                "style": STYLE_RED
            }
        
        # Re-render the display
        self._render_display()
        
        # Small pause to ensure visibility
        time.sleep(0.1)
    
    def update_retry_status(self, data_type: str, retry_delay: int) -> None:
        """Update the status to show a retry is occurring.
        
        Args:
            data_type: The key of the data to update
            retry_delay: Number of seconds until retry
        """
        if data_type not in self.status_data:
            return
            
        self.status_data[data_type] = {
            "status": ICON_RETRYING,
            "details": f"Retrying in {retry_delay} seconds...",
            "style": STYLE_YELLOW_BOLD
        }
        
        # Re-render the display
        self._render_display()
    
    def update_critical_failure(self, data_type: str) -> None:
        """Update the status to show a critical failure.
        
        Args:
            data_type: The key of the data that critically failed
        """
        if data_type not in self.status_data:
            return
            
        self.status_data[data_type] = {
            "status": ICON_CRITICAL,
            "details": "CRITICAL FAILURE - Cannot continue",
            "style": STYLE_BOLD_RED
        }
        
        # Re-render the display
        self._render_display()
    
    def finalize_initialization(self, success: bool) -> None:
        """Finalize the initialization display.
        
        Args:
            success: Whether the overall initialization succeeded
        """
        # Add a summary row to the status data
        if success:
            self.status_data["SUMMARY"] = {
                "status": ICON_SUCCESS,
                "details": "All data loaded successfully",
                "style": STYLE_GREEN_BOLD
            }
        else:
            self.status_data["SUMMARY"] = {
                "status": ICON_CRITICAL,
                "details": "Failed to load critical data. Cannot start TVC Tracker.",
                "style": STYLE_BOLD_RED
            }
        
        # Re-render the display
        self._render_display()
        
        # Pause to ensure visibility
        time.sleep(1.0)