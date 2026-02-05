# =============================================================================
# Copilot Ralph Mode - Development Container
# =============================================================================
# Multi-stage build for optimal caching and smaller image size
# =============================================================================

FROM python:3.11-slim-bookworm AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    # Git and version control
    git \
    git-lfs \
    # Shell utilities
    bash \
    zsh \
    curl \
    wget \
    jq \
    # Process management
    procps \
    htop \
    # Text editors (for quick edits)
    nano \
    vim \
    # Locales
    locales \
    # SSH (for GitHub)
    openssh-client \
    # Node.js + npm (for Copilot CLI)
    nodejs \
    npm \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/*

# Set up locales
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# =============================================================================
# Development stage
# =============================================================================
FROM base AS development

# Create non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub Copilot CLI (node-based)
RUN npm install -g @githubnext/github-copilot-cli

# Set up workspace
WORKDIR /workspace

# Copy requirements first (for better caching)
COPY requirements.txt requirements-dev.txt pyproject.toml ./

# Install Python dependencies (without editable install during build)
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements-dev.txt

# Copy the rest of the project
COPY --chown=$USERNAME:$USERNAME . .

# Ensure VS Code server directories exist and are writable
RUN mkdir -p /home/$USERNAME/.vscode-server/data \
    /home/$USERNAME/.vscode-server/bin \
    /home/$USERNAME/.vscode-server/extensions \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME/.vscode-server

# Make scripts executable
RUN chmod +x ralph_mode.py ralph-loop.sh ralph-mode.sh 2>/dev/null || true \
    && chmod +x .devcontainer/*.sh 2>/dev/null || true

# Switch to non-root user
USER $USERNAME

# Set up shell
ENV SHELL=/bin/zsh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import ralph_mode; print('OK')" || exit 1

# Default command
CMD ["zsh"]
