# Shell completions

Every Suite CLI supports tab completion via `argcomplete`.

## Global activation (bash / zsh)

```bash
activate-global-python-argcomplete --user
# then re-open your shell or:
eval "$(register-python-argcomplete lynx-dashboard)"
```

## Per-command activation

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
eval "$(register-python-argcomplete lynx-mining)"
eval "$(register-python-argcomplete lynx-energy)"
eval "$(register-python-argcomplete lynx-industrials)"
eval "$(register-python-argcomplete lynx-utilities)"
eval "$(register-python-argcomplete lynx-health)"
eval "$(register-python-argcomplete lynx-finance)"
eval "$(register-python-argcomplete lynx-tech)"
eval "$(register-python-argcomplete lynx-comm)"
eval "$(register-python-argcomplete lynx-discretionary)"
eval "$(register-python-argcomplete lynx-staples)"
eval "$(register-python-argcomplete lynx-realestate)"
eval "$(register-python-argcomplete lynx-fundamental)"
eval "$(register-python-argcomplete lynx-compare)"
eval "$(register-python-argcomplete lynx-portfolio)"
eval "$(register-python-argcomplete lynx-dashboard)"
```

## fish

```fish
register-python-argcomplete --shell fish lynx-dashboard | source
# repeat for every CLI you want tab-completion for
```

## Dynamic ticker completion

Sector agents (`lynx-mining`, `lynx-energy`, …) and `lynx-fundamental` / `lynx-compare`
complete the `identifier` / `COMPANY` positional against tickers cached in
`lynx_investor_core.storage`.

`lynx-portfolio` completes `--ticker` against the configured portfolio database
(add / show / delete / update / refresh sub-commands).
