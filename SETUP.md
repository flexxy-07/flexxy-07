# flexxy-07 profile setup

This package is prepared for the existing public repository: https://github.com/flexxy-07/flexxy-07

## What is configured

- The hero portrait embeds the current public GitHub avatar for account ID `183004493` (the PFP returned by the connected GitHub profile).
- `wordmark.svg` is a personalized, monochrome animated terminal wordmark for SUMIT RAJPUT.
- `scripts/generate_streak_svg.py flexxy-07 contrib-heatmap.svg` reads the public contribution calendar for `flexxy-07` and renders a monochrome SVG using actual per-day counts and intensity levels.
- `.github/workflows/update-profile-art.yml` refreshes that SVG every day at 02:00 UTC (07:30 India time) and can also be run manually.

The graph file in this package is intentionally a placeholder, not fabricated activity. It is replaced with actual GitHub contribution data when the workflow first runs.

## Publish to the existing repository (Windows PowerShell)

1. Download and extract this package. The ZIP contains the profile files at its root.
2. Open PowerShell in your existing local clone of `flexxy-07/flexxy-07`.
3. Copy the extracted files into that repository, allowing the updated `README.md`, `wordmark.svg`, `contrib-heatmap.svg`, `scripts/`, and `.github/` to replace the corresponding paths. Do not delete unrelated repository files.
4. Run:

```powershell
git status
git add README.md wordmark.svg contrib-heatmap.svg scripts/generate_streak_svg.py .github/workflows/update-profile-art.yml SETUP.md
git commit -m "feat: personalize terminal profile and contribution graph"
git push origin main
```

## Run the contribution refresh once

1. Open the `flexxy-07/flexxy-07` repository on GitHub.
2. Go to **Settings → Actions → General**.
3. Under **Workflow permissions**, select **Read and write permissions**, then save.
4. Go to **Actions → Update profile art → Run workflow**.
5. When the workflow finishes, refresh your profile. The action commits the generated `contrib-heatmap.svg` automatically.

The scheduled run will keep it refreshed daily. GitHub contribution visibility is subject to GitHub's own contribution rules and settings; by default, public repository activity is shown.

## Notes

- The PFP is embedded from GitHub's avatar CDN; no third-party person's portrait is used. GitHub serves the current avatar for your account.
- The graph is based on GitHub's public contribution calendar for `flexxy-07`, not a fabricated sample or another user's data.
- The connected GitHub integration could read the profile repository but denied writes with HTTP 403 (`Resource not accessible by integration`). The package is prepared locally; it has not been pushed by this session.
