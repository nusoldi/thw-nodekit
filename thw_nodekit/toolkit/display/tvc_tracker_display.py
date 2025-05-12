"""TVC Tracker using Python's Rich library for live terminal output."""

import datetime
import time
from typing import Dict, Any, Optional, List, Union

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich.spinner import Spinner
from rich.box import Box, DOUBLE, ROUNDED, HEAVY, DOUBLE_EDGE

from thw_nodekit import __version__
from thw_nodekit.toolkit.display.base_display import BaseTrackerDisplay
from thw_nodekit.toolkit.core.utils import format_time_remaining, format_timestamp, ensure_utc, convert_timezone
from thw_nodekit.toolkit.core.utils import green, red, bold_yellow, bright_cyan, bold_green

from .constants import (
    STYLE_CYAN, STYLE_BRIGHT_CYAN, STYLE_GREEN, STYLE_GREEN_BOLD, STYLE_RED,
    STYLE_DIM, STYLE_YELLOW_BOLD, STYLE_LINK, STYLE_CYAN_BOLD,
    PADDING_NONE, PADDING_STANDARD, PADDING_NARROW,
    APP_NAME, HEADER_TITLE_TVC
)

# Layout constants
HEADER_SIZE = 3
FOOTER_SIZE = 1
STATUS_SIZE = 5
CLUSTER_INFO_SIZE = 5

class TVCTrackerDisplay(BaseTrackerDisplay):
    """Base class for Rich-based display components with live updates."""
    
    def __init__(self, refresh_rate=20) -> None:
        """Initialize Rich display components.
        
        Args:
            refresh_rate: Display refresh rate in frames per second (default: 20)
        """
        super().__init__()
        self.console = Console()
        self.live = None
        self.last_layout = None
        self.layout = None
        self.refresh_rate = refresh_rate
    
        # Register atexit handler for cleanup
        import atexit
        atexit.register(self.cleanup)
        
        # Create a custom arrow spinner based on the built-in arrow3 spinner in Rich
        left_arrow_frames = ["◃◃◃", "◃◃◂", "◃◂◃", "◂◃◃"]
        right_arrow_frames = ["▹▹▹", "▸▹▹", "▹▸▹", "▹▹▸"]
        # Register custom spinner with Rich
        from rich.spinner import SPINNERS
        SPINNERS["arrow3_left"] = {"interval": 120, "frames": left_arrow_frames}
        self.left_arrow_spinner = Spinner("arrow3_left", style=STYLE_YELLOW_BOLD)
        SPINNERS["arrow3_right"] = {"interval": 120, "frames": right_arrow_frames}
        self.right_arrow_spinner = Spinner("arrow3_right", style=STYLE_YELLOW_BOLD)
    
    def cleanup(self) -> None:
        """Ensure terminal state is restored properly."""
        if self.live:
            try:
                # Stop the live display
                self.live.stop()
                # Clear the screen
                self.console.clear()
                # Alternative direct ANSI clear screen
                print("\033[2J\033[H", end="", flush=True)
                # Explicitly show cursor
                print("\033[?25h", end="", flush=True)
            except Exception:
                # Fallback if normal cleanup fails
                print("\033[2J\033[H", end="", flush=True)  # Clear screen
                print("\033[?25h", end="", flush=True)  # Show cursor
    
    def _create_styled_panel(
        self, 
        content: Any, 
        title: str, 
        title_align: str = "left", 
        border_style: str = STYLE_BRIGHT_CYAN, 
        padding: tuple = PADDING_STANDARD
    ) -> Panel:
        """Create a styled panel with consistent formatting."""
        return Panel(
            content,
            title=Text(title, style=STYLE_GREEN_BOLD),
            title_align=title_align,
            border_style=border_style,
            padding=padding
        )
    
    def _create_basic_table(
        self, 
        show_header: bool = False, 
        box: Any = None, 
        padding: tuple = PADDING_NARROW,
        expand: bool = False, 
        width: Optional[int] = None
    ) -> Table:
        """Create a table with standard configuration."""
        return Table(
            show_header=show_header, 
            box=box, 
            padding=padding,
            expand=expand,
            width=width
        )
    
    def _format_delta_text(
        self, 
        value: int, 
        positive_is_good: bool = True
    ) -> tuple:
        """Format delta values with appropriate colors and text."""
        if value == 0:
            return "(+0)", STYLE_DIM
            
        if value > 0:
            prefix = "+"
            style = STYLE_GREEN if positive_is_good else STYLE_RED
        else:
            prefix = ""  # Negative sign is already included
            style = STYLE_RED if positive_is_good else STYLE_GREEN
            
        return f"({prefix}{value})", style
    
    def format_rich_text(self, text: Union[str, Text], style: Optional[str] = None) -> Text:
        """Convert formatted text strings to Rich Text objects."""
        if not text:
            return Text("")
        
        # Simple mapping of our formatting functions to Rich styles
        if isinstance(text, str):
            if text.startswith('\033[32m'):  # green
                return Text(text.replace('\033[32m', '').replace('\033[0m', ''), style=STYLE_GREEN)
            elif text.startswith('\033[31m'):  # red
                return Text(text.replace('\033[31m', '').replace('\033[0m', ''), style=STYLE_RED)
            elif text.startswith('\033[1;33m'):  # bold_yellow
                return Text(text.replace('\033[1;33m', '').replace('\033[0m', ''), style=STYLE_YELLOW_BOLD)
            elif text.startswith('\033[1;36m'):  # bright_cyan
                return Text(text.replace('\033[1;36m', '').replace('\033[0m', ''), style=STYLE_BRIGHT_CYAN)
            elif text.startswith('\033[1;32m'):  # bold_green
                return Text(text.replace('\033[1;32m', '').replace('\033[0m', ''), style=STYLE_GREEN_BOLD)
            else:
                return Text(text, style=style)
        return text
        
    def create_rich_header(self, title: str) -> Panel:
        """Create a standardized header for Rich display."""
        
        header_text = Text()
        header_text.append(f"{APP_NAME}: ", style=STYLE_GREEN_BOLD)

        header_text.append(f"{title}", style=STYLE_CYAN_BOLD)
        header_text.append(" • ", STYLE_DIM)
        header_text.append(f"v{__version__}", style=STYLE_DIM)
        header_text = Align.center(header_text)
        
        return Panel(header_text, border_style=STYLE_GREEN_BOLD, box=DOUBLE_EDGE, padding=PADDING_NONE)

    def update_display(self):
        """Update the display with the current layout."""
        if not self.live:
            # First time display - create Live context
            self.live = Live(
                self.layout, 
                console=self.console, 
                refresh_per_second=self.refresh_rate, 
                screen=True, 
                transient=False
            )
            
            # Clear screen before starting to prevent overlap with previous content
            self.console.clear()
            self.live.start()
        else:
            # Update existing display
            self.live.update(self.layout)
            
    def _format_time_remaining(self, time_remaining: Union[str, int, datetime.timedelta]) -> str:
        """Format time remaining in the specified format."""
        return format_time_remaining(time_remaining)

    def create_layout(self) -> Layout:
        """Create the initial layout structure."""
        layout = Layout()
        
        # blank_space = Text("")

        layout.split(
            Layout(name="header", size=HEADER_SIZE),
            Layout(name="cluster_info", size=CLUSTER_INFO_SIZE),
            Layout(name="main_area", ratio=1),
            Layout(name="status", size=STATUS_SIZE)
        )
        
        # layout["spacer"].update(blank_space)

        # Split the main area into a left and right section
        layout["main_area"].split_row(
            Layout(name="left_panels", ratio=3),
            Layout(name="right_panels", ratio=2)
        )
        
        # Split the left panels vertically
        layout["left_panels"].split(
            Layout(name="validator_info", ratio=8),
            Layout(name="geolocation_info", ratio=7),
            Layout(name="epoch_info", ratio=7),
            Layout(name="leader_info", ratio=10),
        )
        
        # Split the right panels vertically
        layout["right_panels"].split(
            Layout(name="vote_metrics", ratio=1),
            Layout(name="comparisons", ratio=3)
        )
        
        return layout
    
    def _build_comparison_table(self, comparisons: List[Dict[str, Any]]) -> Table:
        """Build a comparison table for vote credit differences."""
        table = self._create_basic_table()
        
        # Define a 4-column structure for better alignment control
        table.add_column(justify="right")   # "Rank" text
        table.add_column(justify="right")  # Rank number 
        table.add_column(justify="left")  # Diff value (numbers)
        table.add_column(justify="left")   # "credits" text
        
        for comp in comparisons:
            rank = comp["rank"]
            diff = comp["diff"]
            is_current = comp.get("is_current", False)
            
            # Format rank components
            if is_current:
                # Create a custom table for the rank indicator with spinner
                inline_table = Table(show_header=False, box=None, padding=PADDING_NONE)
                inline_table.add_column()  # Column for spinner
                inline_table.add_column()  # Column for text
                inline_table.add_row(
                    self.right_arrow_spinner,
                    Text(" Rank", style=STYLE_GREEN_BOLD)
                )
                rank_label = inline_table
                rank_value = Text(f"{rank}:", style=STYLE_GREEN_BOLD)
            else:
                rank_label = Text("Rank")
                rank_value = Text(f"{rank}:")
            
            # Format diff components based on value
            if diff > 0:
                diff_value = Text(f"+{diff}", style=STYLE_RED)
                credits_label = Text("credits", style=STYLE_RED)
            elif diff < 0:
                diff_value = Text(f"{diff}", style=STYLE_GREEN)
                credits_label = Text("credits", style=STYLE_GREEN)
            else:
                if is_current:
                    # Create a custom table for "YOUR POSITION" with spinner
                    diff_value = Text("CURRENT", style=STYLE_BRIGHT_CYAN)
                    
                    inline_diff_table = Table(show_header=False, box=None, padding=PADDING_NONE)
                    inline_diff_table.add_column()  # Column for text
                    inline_diff_table.add_column()  # Column for spinner
                    inline_diff_table.add_row(
                        Text("POSITION ", style=STYLE_BRIGHT_CYAN),
                        self.left_arrow_spinner
                    )
                    credits_label = inline_diff_table
                else:
                    diff_value = Text("0")
                    credits_label = Text("credits")
            
            # Add all four components to the row
            table.add_row(rank_label, rank_value, diff_value, credits_label)
        
        return table
    
    def _update_cluster_info(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the cluster info panel."""
        cluster_table = self._create_basic_table(padding=PADDING_NARROW)
        
        cluster_table.add_column(justify="left")
        cluster_table.add_column(justify="center", width=1)
        cluster_table.add_column(justify="left")
        cluster_table.add_column(justify="center", width=1)
        cluster_table.add_column(justify="left")
        
        cluster_info = Text()
        cluster_info.append("Cluster: ", style=STYLE_BRIGHT_CYAN)
        cluster_info.append(str(data.get('cluster_type', 'Unknown')))
        
        node_count = Text()
        node_count.append("Node Count: ", style=STYLE_BRIGHT_CYAN)
        node_count.append(f"{data.get('active_node_count', 0):,}")
        
        rpc_url = Text()
        rpc_url.append("RPC URL: ", style=STYLE_BRIGHT_CYAN)
        rpc_url.append(data.get("rpc_url", "Unknown"))
        
        divider = Text("│", style=STYLE_BRIGHT_CYAN)
        
        cluster_table.add_row(
            cluster_info,
            divider,
            node_count,
            divider,
            rpc_url
            )
        
        panel = self._create_styled_panel(
            Align.left(cluster_table),
            "Cluster Info", 
            title_align="left",
            padding=PADDING_STANDARD
        )
        layout["cluster_info"].update(panel)
    
        
    def _update_validator_info(
        self, 
        layout: Layout, 
        data: Dict[str, Any], 
        validator_identity: str
    ) -> None:
        """Update the validator information panel."""
        validator = data["validator"]
        validator_name = data["validator_name"]
        version = data.get("version", "Unknown")
        
        validator_table = self._create_basic_table()
        
        # Add rows with labels and values - ONLY validator specific info
        validator_table.add_row(
            Text("Validator Name:", style=STYLE_BRIGHT_CYAN), 
            Text(validator_name, style=STYLE_GREEN_BOLD)
        )
        validator_table.add_row(
            Text("Identity Pubkey:", style=STYLE_BRIGHT_CYAN), 
            Text(validator_identity)
        )
        
        vote_pubkey = validator.get("votePubkey", "Unknown")
        validator_table.add_row(
            Text("Vote Pubkey:", style=STYLE_BRIGHT_CYAN), 
            Text(vote_pubkey)
        )
        
        validator_table.add_row(
            Text("Active Stake:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{int(validator.get('activatedStake', 0)) / 1_000_000_000:,.2f} ◎")
        )
        
        validator_table.add_row(
            Text("Version:", style=STYLE_BRIGHT_CYAN), 
            Text(version)
        )

        # Add external links
        self._add_external_links(validator_table, data, validator_identity, vote_pubkey)
        
        panel = self._create_styled_panel(validator_table, "Validator Info")
        layout["validator_info"].update(panel)
    
    def _add_external_links(
        self, 
        table: Table, 
        data: Dict[str, Any], 
        validator_identity: str, 
        vote_pubkey: str
    ) -> None:
        """Add external links to the validator table."""
        # Add validators.app link
        network = "mainnet" if data.get("cluster_type") == "Mainnet" else "testnet"
        validators_app_url = f"https://www.validators.app/validators/{validator_identity}?locale=en&network={network}"
        table.add_row(
            Text("Validators.app:", style=STYLE_BRIGHT_CYAN), 
            Text.from_markup(f"[link={validators_app_url}]View on Validators.app[/link]", style=STYLE_LINK)
        )
        
        # Add SVT.one dashboard link if vote pubkey is available
        if vote_pubkey != "Unknown":
            cluster_param = "?cluster=testnet" if data.get("cluster_type") != "Mainnet" else ""
            svt_url = f"https://svt.one/dashboard/{vote_pubkey}{cluster_param}"
            table.add_row(
                Text("SVT.one:", style=STYLE_BRIGHT_CYAN), 
                Text.from_markup(f"[link={svt_url}]View on SVT.one[/link]", style=STYLE_LINK)
            )
            
            # Add StakeWiz link only for mainnet validators
            if data.get("cluster_type") == "Mainnet":
                stakewiz_url = f"https://stakewiz.com/validator/{vote_pubkey}"
                table.add_row(
                    Text("StakeWiz:", style=STYLE_BRIGHT_CYAN),
                    Text.from_markup(f"[link={stakewiz_url}]View on StakeWiz[/link]", style=STYLE_LINK)
                )
    
    def _update_geolocation_info(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the geolocation info panel."""
        ip_address = data["ip_address"]
        ip_info = data.get("ip_info", {})
        
        # Format location info
        city = ip_info.get("city", "")
        country = ip_info.get("country_name", ip_info.get("country", ""))
        ip_location = f"{city}, {country} ({ip_info.get('country', '')})"
        
        # Format datacenter/ASN info
        va_format = ip_info.get("va_format", "Unknown")
        asn = ip_info.get("asn", "Unknown")
        organization = ip_info.get("org_name", "Unknown")
        
        geolocation_table = self._create_basic_table()
        
        # Add geolocation rows
        geolocation_table.add_row(Text("IP Address:", style=STYLE_BRIGHT_CYAN), Text(ip_address))
        geolocation_table.add_row(Text("Location:", style=STYLE_BRIGHT_CYAN), Text(ip_location))
        geolocation_table.add_row(Text("Datacenter:", style=STYLE_BRIGHT_CYAN), Text(va_format))
        geolocation_table.add_row(Text("ASN:", style=STYLE_BRIGHT_CYAN), Text(asn))
        geolocation_table.add_row(Text("ASO:", style=STYLE_BRIGHT_CYAN), Text(organization))
        
        # Add IPInfo link
        ipinfo_url = f"https://ipinfo.io/{ip_address}"
        geolocation_table.add_row(
            Text("IPInfo:", style=STYLE_BRIGHT_CYAN),
            Text.from_markup(f"[link={ipinfo_url}]View on IPInfo[/link]", style=STYLE_LINK)
        )
        
        # Add Ping Test link
        ping_test_url = f"https://ping.pe/{ip_address}"
        geolocation_table.add_row(
            Text("Ping Test:", style=STYLE_BRIGHT_CYAN),
            Text.from_markup(f"[link={ping_test_url}]View Ping Test[/link]", style=STYLE_LINK)
        )
        
        panel = self._create_styled_panel(geolocation_table, "Geolocation Info")
        layout["geolocation_info"].update(panel)
    
    def _update_epoch_info(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the epoch information panel."""
        metrics = data["epoch_metrics"]
        
        epoch_table = self._create_basic_table()
        
        # Create a visual progress bar
        progress_percent = metrics['percent_complete']
        bar_width = 16  # Characters for the progress bar
        filled_width = int(bar_width * progress_percent / 100)
        empty_width = bar_width - filled_width
        
        # Build progress bar with gradient coloring
        progress_bar = Text()
        progress_bar.append("▓" * filled_width, style="green")
        progress_bar.append("░" * empty_width, style="dim")
        progress_bar.append(f" {progress_percent:.4f} %")
        
        # Add rows with epoch data
        epoch_table.add_row(Text("Current Epoch:", style=STYLE_BRIGHT_CYAN), str(metrics["epoch"]))
        epoch_table.add_row(Text("Percent Complete:", style=STYLE_BRIGHT_CYAN), progress_bar)
        epoch_table.add_row(Text("Slots Complete:", style=STYLE_BRIGHT_CYAN), f"{metrics['slot_index']} / {metrics['slots_in_epoch']} ({metrics['remaining_slots']} remaining)")
        epoch_table.add_row(Text("Avg Slot Time:", style=STYLE_BRIGHT_CYAN), f"{metrics['avg_slot_time']:.4f} seconds")
        # epoch_table.add_row(Text("Estimated End:", style=STYLE_BRIGHT_CYAN), Text(f"{metrics['estimated_end_time'].strftime('%Y-%m-%d %H:%M:%S')} | {metrics['estimated_end_time'].strftime('%a %b %d, %I:%M %p').replace(' 0', ' ').replace(':0', ':')}"))
        
        # Ensure estimated end time is in UTC
        est_end_time_utc = ensure_utc(metrics['estimated_end_time'])
        
        # Add UTC time
        epoch_table.add_row(
            Text("Estimated End (UTC):", style=STYLE_BRIGHT_CYAN), 
            Text(format_timestamp(est_end_time_utc, format_type="both"))
        )
        
        # Convert to EST and add EST time
        est_end_time_est = convert_timezone(est_end_time_utc, "America/New_York")
        epoch_table.add_row(
            Text("Estimated End (EST):", style=STYLE_BRIGHT_CYAN), 
            Text(format_timestamp(est_end_time_est, format_type="both"))
        )

        epoch_table.add_row(Text("Time Remaining:", style=STYLE_BRIGHT_CYAN), format_time_remaining(metrics.get("time_remaining_seconds", metrics["time_remaining"])))
        # epoch_table.add_row(Text(" "))

        # Create panel using the same method as other panels
        panel = self._create_styled_panel(epoch_table, "Epoch Info")
        layout["epoch_info"].update(panel)
        
    def _update_leader_info(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the leader information panel."""
        # Get leader metrics - first check if new format metrics are available
        leader_metrics = data.get("leader_metrics", {})
        
        leader_table = self._create_basic_table()
        
        # Add leader info rows
        leader_table.add_row(
            Text("Total Leader Slots:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{leader_metrics.get('leader_slots_total', 0)} slots")
        )
        
        leader_table.add_row(
            Text("Completed Leader Slots:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{leader_metrics.get('leader_slots_completed', 0)} slots")
        )
        
        leader_table.add_row(
            Text("Upcoming Leader Slots:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{len(leader_metrics.get('leader_slots_upcoming', []))} slots")
        )
        
        leader_table.add_row(
            Text("Blocks Produced:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{leader_metrics.get('blocks_produced', 'N/A')}")
        )
        
        leader_table.add_row(
            Text("Slots Skipped:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{leader_metrics.get('leader_slots_skipped', 'N/A')}")
        )
        
        # Add skip rate with color based on value
        skip_rate = leader_metrics.get('skip_rate', 0)
        skip_rate_style = STYLE_RED if skip_rate > 0 else STYLE_GREEN
        leader_table.add_row(
            Text("Skip Rate:", style=STYLE_BRIGHT_CYAN), 
            Text(f"{skip_rate:.2f}%", style=skip_rate_style)
        )

        # Add next leader slot info if available
        next_slot = leader_metrics.get('leader_slot_next')
        if next_slot is not None:
            leader_table.add_row(
                Text("Next Leader Slot:", style=STYLE_BRIGHT_CYAN), 
                Text(f"{next_slot}")
            )
            
            # Add next leader time if available
            next_time = leader_metrics.get('leader_slot_time')
            if next_time is not None:
                # Ensure the time is in UTC
                next_time_utc = ensure_utc(next_time)
                
                # Display UTC time
                leader_table.add_row(
                    Text("Next Leader Time (UTC):", style=STYLE_BRIGHT_CYAN), 
                    Text(format_timestamp(next_time_utc, format_type="both"))
                )
                
                # Convert to EST and display
                next_time_est = convert_timezone(next_time_utc, "America/New_York")
                leader_table.add_row(
                    Text("Next Leader Time (EST):", style=STYLE_BRIGHT_CYAN), 
                    Text(format_timestamp(next_time_est, format_type="both"))
                )
                
                # Add time remaining
                time_remaining = leader_metrics.get('leader_slot_time_remaining')
                if time_remaining is not None:
                    leader_table.add_row(
                        Text("Time Until Next:", style=STYLE_BRIGHT_CYAN), 
                        Text(format_time_remaining(time_remaining))
                    )
        
        # Create panel
        panel = self._create_styled_panel(leader_table, "Leader Info")
        layout["leader_info"].update(panel)
        
    def _update_vote_metrics(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the vote metrics panel."""
        validator = data["validator"]
        epoch_credits = data["epoch_credits"]
        missed_credits = data["missed_credits"]
        last_vote = data["last_vote"]
        root_slot = data["root_slot"]
        percentile = data.get("network_stats", {}).get("percentile", 0)
        
        vote_metrics_table = self._create_basic_table(
            show_header=True, 
            expand=False, 
            width=40
        )

        # Add columns with center alignment
        vote_metrics_table.add_column(Text("Metric", style=STYLE_CYAN), justify="left", style=STYLE_BRIGHT_CYAN)
        vote_metrics_table.add_column(Text("Current", style=STYLE_CYAN), justify="left")
        vote_metrics_table.add_column(Text("Delta", style=STYLE_CYAN), justify="left")

        rank_value = data.get('validator_rank', 'N/A')
        rank_delta = data.get('rank_delta', 0)
        rank_delta_text, rank_delta_style = self._format_delta_text(rank_delta, positive_is_good=False)
        vote_metrics_table.add_row(
            Text("Epoch Rank:"), 
            Text(f"{rank_value}", style=STYLE_GREEN_BOLD),
            Text(rank_delta_text, style=rank_delta_style)
        )
        
        credit_delta = data.get('credit_delta', 0)
        credit_delta_text, credit_delta_style = self._format_delta_text(credit_delta, positive_is_good=True)
        vote_metrics_table.add_row(
            Text("Epoch Credits:"), 
            Text(f"{epoch_credits:,}"),
            Text(credit_delta_text, style=credit_delta_style)
        )
        
        missed_delta = data.get('missed_delta', 0)
        missed_delta_text, missed_delta_style = self._format_delta_text(missed_delta, positive_is_good=False)
        vote_metrics_table.add_row(
            Text("Missed Credits:"), 
            Text(f"{missed_credits:,}"),
            Text(missed_delta_text, style=missed_delta_style)
        )
        
        vote_slot_delta = data.get('vote_slot_delta', 0)
        vote_metrics_table.add_row(
            Text("Last Vote:"), 
            Text(f"{last_vote:,}"),
            Text(f"(+{vote_slot_delta})", style=STYLE_DIM)
        )
        
        root_slot_delta = data.get('root_slot_delta', 0)
        vote_metrics_table.add_row(
            Text("Root Slot:"), 
            Text(f"{root_slot:,}"),
            Text(f"(+{root_slot_delta})", style=STYLE_DIM)
        )

        percentile_style = STYLE_GREEN if percentile > 50 else STYLE_DIM
        vote_metrics_table.add_row(
            Text("Percentile:"), 
            Text(f"{percentile:.2f}%", style=percentile_style),
            Text("")
        )
        
        panel = self._create_styled_panel(
            Align.center(vote_metrics_table),
            "Vote Metrics", 
            title_align="center",
            padding=PADDING_STANDARD
        )
        layout["vote_metrics"].update(panel)
    
    def _update_comparisons(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the comparisons panel."""
        comparison_table = self._build_comparison_table(data.get("rank_comparisons", []))
        
        panel = self._create_styled_panel(
            Align.center(comparison_table),
            "Vote Credit Differences", 
            title_align="center",
            padding=PADDING_STANDARD
        )
        layout["comparisons"].update(panel)
        
    def _update_status(self, layout: Layout, data: Dict[str, Any]) -> None:
        """Update the status panel with spinner to indicate active status."""
        status_table = self._create_basic_table(padding=PADDING_NARROW)
        
        # Add columns
        status_table.add_column(justify="left")
        status_table.add_column(justify="center", width=1)  # Center column for divider
        status_table.add_column(justify="right")
        status_table.add_column(justify="left")
        status_table.add_column(justify="center", width=1)  # Center column for divider
        status_table.add_column(justify="right")

        # Create spinner and timestamp
        spinner = Spinner("dots", text=Text("Tracking",STYLE_BRIGHT_CYAN), style=STYLE_GREEN_BOLD)
        quit_message = Text("Press Ctrl+C to quit", style=STYLE_YELLOW_BOLD)
        cache_info_label = Text("Cache:", style=STYLE_BRIGHT_CYAN)
        divider = Text("│", style=STYLE_BRIGHT_CYAN)
        
        # Format cache ages
        cache_ages = data.get('cache_ages', {})
        
        cache_info_text = Text()
        
        # Group cache ages by category
        high_freq = []
        med_freq = []
        low_freq = []
        
        for key, age in cache_ages.items():
            if key in ['vote_accounts', 'epoch_info', 'slot']:
                high_freq.append(f"{key.replace('get_', '')}: {age}s")
            elif key in ['leader_schedule', 'block_production']:
                med_freq.append(f"{key.replace('get_', '')}: {age}s")
            else:
                low_freq.append(f"{key.replace('get_', '')}: {age}s")
        
        # Add high-frequency items with emphasis
        if high_freq:
            cache_info_text.append(" ".join(high_freq), style=STYLE_GREEN_BOLD)
        
        # Add medium-frequency items
        if med_freq:
            if high_freq:
                cache_info_text.append(" • ", style=STYLE_DIM)
            cache_info_text.append(" ".join(med_freq))
        
        # Add low-frequency items
        if low_freq:
            if high_freq or med_freq:
                cache_info_text.append(" • ", style=STYLE_DIM)
            cache_info_text.append(" ".join(low_freq), style=STYLE_DIM)
        
        # Add row with spinner, timestamp, cache info, and quit message
        status_table.add_row(
            spinner,
            divider,
            cache_info_label,
            cache_info_text,
            divider,
            quit_message
            )
        
        panel = self._create_styled_panel(
            Align.center(status_table),
            "Status", 
            title_align="center",
            padding=PADDING_STANDARD
        )
        layout["status"].update(panel)
    
    def display_validator_data(self, data: Dict[str, Any], validator_identity: str) -> None:
        """Display validator data using Rich for flicker-free updates."""
        if not data:
            self._display_not_found_message(validator_identity)
            return
        
        # Create layout
        self.layout = self.create_layout()
        
        # Update all panels
        self.layout["header"].update(self.create_rich_header(HEADER_TITLE_TVC))
        self._update_cluster_info(self.layout, data)
        self._update_validator_info(self.layout, data, validator_identity)
        self._update_geolocation_info(self.layout, data)
        self._update_epoch_info(self.layout, data)
        self._update_leader_info(self.layout, data)
        self._update_vote_metrics(self.layout, data)
        self._update_comparisons(self.layout, data)
        self._update_status(self.layout, data)
        
        # Display the layout
        self.update_display()
    
    def _display_not_found_message(self, validator_identity: str) -> None:
        """Display a message when validator is not found."""
        self.layout = self.create_layout()
        self.layout["header"].update(self.create_rich_header(HEADER_TITLE_TVC))
        self.layout["validator_info"].update(
            Text(f"Validator {validator_identity} not found in the current data.")
        )
        
        self.update_display() 