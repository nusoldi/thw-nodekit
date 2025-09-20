# THW-NodeKit

**THW-NodeKit** is a toolkit for Solana validator **operatoooooooooors**, created by Nu_Soldi ([@nusoldi](https://github.com/nusoldi), [@Nu_Soldi](https://x.com/Nu_Soldi)) on behalf of **THW Validator** ([trulyhonestwork.io](https://trulyhonestwork.io/), [@trulyhonestwork](https://x.com/trulyhonestwork)). *It ain't much, but it's Truly Honest Work™.*


***Note from the creator***: *This project was originally created to simplify a bunch of random bash scripts and tools into a singular CLI for personal ease-of-use. The implementation is Python-based due to experience in the language. It is being shared publically in the case it helps anyone else in the community. We welcome feedback/collaboration on future enhancements.*


## Core Components
THW-NodeKit provides a unified command-line interface (CLI) with various functions for Solana validator operators, and is primarily composed of two major components:

*   **`Buildkit`**: Builds Solana validator clients from source files.
*   **`Toolkit`**: Provides various utility tools and a Live TVC tracker.

## Key Features

*   **`Buildkit` Details**:
    *   Currently, supports builds `build` for the primary validator clients: **Agave**, **Jito**, and **Firedancer**.
    *   Allows installation from official repositories or custom (i.e. mod) repositories.
    *   Control over build threads/jobs to ensure new releases can safely be installed on live/voting nodes
*   **`Toolkit` Details**:
    *   Real-time TVC tracker `tvc` for any validator on mainnet (um) or testnet (ut).
    *   Validator identity swap command `failover` for robust and efficient validator failovers
    *   Snapshot downloads via the Avorio network `snap-avorio`  or the Snapshot Finder tool `snap-finder`
    *   Affinity command `affinity` to set the Agave PoH thread to a specific core
    *   Symlink command `symlink` to update the active_release based on the client/version (TAG)
*   **Simplified Configuration**: Central configuration TOML file to easily manage settings.

## Attribution

*   **`snap-finder`**: This is a fork of the well-known [solana-snapshot-finder](https://github.com/c29r3/solana-snapshot-finder). All credit goes to **[@c29r3](https://github.com/c29r3)** for the original implementation .
*   **`snap-avorio`**: This uses the Avorio snapshots mirror ([avorio.network/snapshots](https://avorio.network/snapshots/)). All credit goes to the originators.
*   **`affinity`**: This is based on a script shared in the Solana Tech Discord by ax of 1000x.sh ([@1000xsh](https://github.com/1000xsh), [@ax_1000x](https://x.com/ax_1000x)).

## Prerequisites

To successfully install and run THW-NodeKit, ensure your system meets the following requirements:

*   **Operating System**: Linux (only tested on Ubuntu).
*   **Python**: Version 3.6 or higher.
*   **PIP**: Python package installer for Python 3.
    **Python Packages**: See the `requirements.txt` file for details, the install script will automatically install these.
*   **Git**: For cloning the repository.
*   **Build Essentials**: Necessary for compiling Solana client source code.
    ```bash
    sudo apt update
    sudo apt install -y python3 python3-pip git build-essential pkg-config libssl-dev
    ```
*   **aria2c**: For downloading snapshots efficiently using the `snap-avorio` command.
    ```bash
    sudo apt install -y aria2
    ```


## Installation

Follow these steps to install THW-NodeKit:

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/nusoldi/thw-nodekit.git
    ```

2.  **Navigate to the Directory**:
    ```bash
    cd thw-nodekit
    ```

3.  **Run the Installation Script**:
    This script will install dependencies locally within the project's `lib/` directory and create a symlink for the `thw-nodekit` executable.
    ```bash
    ./install.sh
    ```

4.  **Update Your PATH (Recommended)**:
    For convenient access to the `thw-nodekit` command, add `~/.local/bin` to your shell's PATH:
    ```bash
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    ```
    *Note: If you are using a shell other than bash (e.g., zsh), update the respective configuration file (e.g., `~/.zshrc`).*

5.  **Verify Installation**:
    If you've updated your PATH:
    ```bash
    thw-nodekit --help
    ```
    If you haven't updated your PATH, you can run it directly:
    ```bash
    ~/thw-nodekit/bin/thw-nodekit --help
    ```

## Configuration

THW-NodeKit uses `config.default.toml` for its default settings. It's highly recommended to create a local override configuration to customize settings without modifying the default file.

1.  **Create a Local Configuration File**:
    ```bash
    cp config.default.toml config.local.toml
    ```

2.  **Customize Settings**:
    Edit `config.local.toml` to adjust parameters such as:
    *   RPC endpoints
    *   Repository URLs for modified validator clients
    *   Default installation paths
    *   Build parameters
    *   Snapshot directories



## `Buildkit`: Usage

The `build` component is used for building and installing various Solana validator clients from source files. **Important:** configuration of install directories is done in the config TOML file. Be sure to review and update before using. The command will build the binaries following the below directory structure:

`~/.local/share/solana/install/releases/$CLIENT/$TAG`


For example: `~/.local/share/solana/install/releases/jito/v2.1.18-jito`

#### `build`: Build and Install Solana Clients

*   **Arguments**:
    *   `client` (Required): The client to build.
        *   Choices: `agave`, `jito`, `firedancer`
    *   `type` (Required): The type of repository to build from.
        *   Choices: `official`, `mod` (ensure corresponding URLs are in your configuration for `mod`).
    *   `tag` (Required): The release tag (e.g., `v2.1.11`) or branch name to build.
    *   `update_symlink` (Required): Whether to update the `active_release` symlink.
        *   Choices: `true`, `false`
    *   `build_threads` (Optional): Number of parallel build threads. Defaults to the value in your configuration.
        *   Example: `8`
*   **Syntax**:
    ```bash
    thw-nodekit build <client> <type> <tag> <update_symlink> [build_threads]
    ```
*   **Examples**:
    *   Build Agave (Official Release), update symlink to active_release, using default build threads:
        ```bash
        thw-nodekit build agave official v2.1.11 true
        ```
    *   Build Jito (Custom Mod Release), update symlink active_release, using 16 build threads:
        *(Ensure `config.local.toml` has `jito_mod` URL set, assumes TAG/release available called `v2.1.18-mod`)*
        ```bash
        thw-nodekit build jito mod v2.1.18-mod true 16
        ```
    *   Build Firedancer (Official Release), do NOT update symlink to active_release:
        ```bash
        thw-nodekit build firedancer official v0.401.20113 false
        ```
![image](https://github.com/user-attachments/assets/68f0d25e-8fc0-4353-95bc-5c464f8022ec)

---

## `Toolkit`: Usage

The `Toolkit` provides various utilities for validator management and monitoring.

---

#### `tvc`: Live TVC Tracker

Tracks vote credits in real-time for a specified validator.  

*Note 1: It is advised to not run this monitor on a live node given the heavy RPC calls required. We run it on our monitoring VPS with minimal specs (4 GB RAM / 2 vCPUs) and it runs great (alongside Grafana/Watchtower/etc).*

*Note 2: The console window will automatically resize when you zoom in/out. Use Ctrl + +/- on most consoles to do this (i.e. Ctrl + - (Ctrl and Minus key) to zoom out so it fits)*

*Note 3: The way `missed_credits` are calculated is against the Rank 1 validator in the cluster, rather than a hypothetical "optimal" validator (such as how vxtools measures it). We took this approach for simplicity as the difference between TVC ranks is primarily what we're looking to measure.*

*   **Arguments**:
    *   `cluster` (Required): Cluster to use.
        *   Choices: `um` (Mainnet-beta), `ut` (Testnet)
    *   `identity` (Optional): Validator identity public key. Uses default from config if not provided.
    *   `--interval <seconds>` or `-i <seconds>` (Optional): Display refresh interval.
        *   Default: `1.0`
*   **Syntax**:
    ```bash
    thw-nodekit tvc <cluster> [identity] [-i <interval>]
    ```
*   **Examples**:
    *   Monitor TVC for a specific validator on Mainnet, default interval:
        ```bash
        thw-nodekit tvc um YOUR_VALIDATOR_IDENTITY_PUBKEY
        ```
    *   Monitor TVC for the configured default validator on Testnet, 5s interval:
        ```bash
        thw-nodekit tvc ut --interval 5
        ```

---

#### `affinity`: Manage CPU Affinity

Sets the CPU affinity for the Agave PoH (Proof of History) thread.


*Note: Command was specifically written to not require sudo access. The user running the command must be the same one that's running the Solana service, otherwise it requires sudo access. For example, if the 'sol' user runs the Solana service, the 'sol' user will be able to run this command without error.*

*   **Arguments**:
    *   `--core <number>` (Optional): Specify the CPU core number. Overrides `toolkit.poh_core` in the configuration.
*   **Syntax**:
    ```bash
    thw-nodekit affinity [--core <number>]
    ```
*   **Examples**:
    *   Set affinity using the core defined in `config.local.toml`:
        ```bash
        thw-nodekit affinity
        ```
    *   Set affinity to CPU core `3`:
        ```bash
        thw-nodekit affinity --core 3
        ```

---

#### `snap-avorio`: Download Snapshots from Avorio

Downloads full or incremental snapshots from the Avorio network. `aria2c` must be installed.


*Note: At time of writing, the Avorio network appears to be down for Testnet snapshots. This is unrelated to this command/project and is out of our control. Mainnet snapshots appear to be working fine*

*   **Arguments**:
    *   `cluster` (Required): Cluster to download for.
        *   Choices: `um` (Mainnet-beta), `ut` (Testnet)
    *   `snap_type` (Required): Type of snapshot.
        *   Choices: `full`, `incr`, `both`
*   **Syntax**:
    ```bash
    thw-nodekit snap-avorio <cluster> <snap_type>
    ```
*   **Examples**:
    *   Download the latest full snapshot for Mainnet:
        ```bash
        thw-nodekit snap-avorio um full
        ```
    *   Download the latest incremental snapshot for Mainnet:
        ```bash
        thw-nodekit snap-avorio um incr
        ```
    *   Download both full and incremental snapshots for Testnet:
        ```bash
        thw-nodekit snap-avorio ut both
        ```
![image](https://github.com/user-attachments/assets/dc8ae844-9eaf-4e43-b0f6-c96809e12e8c)

---

#### `snap-finder`: Find and Download Snapshots from Gossip

Finds and downloads the latest available snapshot by querying RPC nodes in gossip.

*Note: Uses hardcoded default arguments from the original implementation [solana-snapshot-finder](https://github.com/c29r3/solana-snapshot-finder) for simplicity. This is a WIP and will be updated later.*

*   **Arguments**:
    *   `cluster` (Required): Cluster to find snapshot for.
        *   Choices: `um` (Mainnet-beta), `ut` (Testnet)
*   **Syntax**:
    ```bash
    thw-nodekit snap-finder <cluster>
    ```
*   **Examples**:
    *   Find and download the latest snapshots for Mainnet:
        ```bash
        thw-nodekit snap-finder um
        ```
![image](https://github.com/user-attachments/assets/a178d0d0-5687-46bd-bcb0-7721c54b8a0c)

---

#### `symlink`: Manage `active_release` Symlink

Creates or updates the `active_release` symlink for a specified Solana client version. **Important:** assumes a specific directory structure is in place: `~/.local/share/solana/install/releases/$CLIENT/$TAG`

*   **Arguments**:
    *   `client` (Required): The client to symlink.
        *   Choices: `agave`, `jito`, `firedancer`
    *   `tag` (Required): The release tag (e.g., `v2.1.11`) that is already built/installed.
*   **Syntax**:
    ```bash
    thw-nodekit symlink <client> <tag>
    ```
*   **Examples**:
    *   Update symlink to point to Agave version `v2.1.11`:
        ```bash
        thw-nodekit symlink agave v2.1.11
        ```
    *   Update symlink to point to Jito version `v2.1.18-jito`:
        ```bash
        thw-nodekit symlink jito v2.1.18-jito
        ```
![image](https://github.com/user-attachments/assets/04b90173-0146-43a0-803a-0a0076c92623)

---

#### `failover`: Perform Validator Identity Swap (Failover)

Orchestrates a nearly instantaneous identity swap (failover) between two validator nodes: an active (local) node and an inactive 'hotspare' (remote) node. This command automates the process of changing identities, transferring the tower file, and updating symlinks on both nodes to ensure a seamless transition.

*Note: This command is a powerful tool that performs significant changes on both nodes. It is critical to have your `config.local.toml` file correctly configured for both the active (`from_host`) and inactive (`to_host`) nodes before execution. The script performs extensive pre-flight checks to validate configurations and paths on both machines before prompting for final confirmation.*

*   **Arguments**:
    *   `from_host` (Required): The hostname of the currently **ACTIVE** (local) node, as defined in your config file. The script must be run from this node.
    *   `to_host` (Required): The hostname of the **INACTIVE** (remote) node, as defined in your config file.
    *   `cluster` (Required): The cluster context for the failover.
        *   Choices: `mainnet`, `testnet`
*   **Configuration**:
    *   Your `config.local.toml` must contain sections for both hosts, using the format `[<hostname>.<cluster>]`. For example: `[validator-1.mainnet]` and `[validator-2.mainnet]`.
    *   Each host's configuration section must be fully populated with correct paths (ledger, keypairs, solana binaries) and SSH details (user, ip, key path).
*   **Syntax**:
    ```bash
    thw-nodekit failover <from_host> <to_host> <cluster>
    ```
*   **Examples**:
    *   Perform a failover from `validator-1` to `validator-2` on `mainnet`:
        ```bash
        thw-nodekit failover validator-1 validator-2 mainnet
        ```
        
---

#### Other `Toolkit` Commands (Future Development)

Additional commands and utilities for the `Toolkit` are planned and will be detailed here as they become available.

## Uninstallation

To remove THW-NodeKit from your system:

1.  **Remove the Symlink** (if created):
    ```bash
    rm ~/.local/bin/thw-nodekit
    ```

2.  **Delete the Installation Directory**:
    ```bash
    rm -rf ~/thw-nodekit  # Or the directory where you cloned it
    ```

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the `LICENSE` file for more details.

---
