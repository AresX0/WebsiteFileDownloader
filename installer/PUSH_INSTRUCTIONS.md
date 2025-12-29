How to push a branch and (optionally) merge it to `main` using a GitHub Personal Access Token (PAT)

If you can push to the repository directly, you won't need a token; use your configured credentials.
If you need to use a PAT (for automation or for a machine that doesn't have your account credentials):

1) Create a token
- Visit https://github.com/settings/tokens
- Click "Generate new token" (classic) or create a fine-grained token
- Give it the `repo` scope (and `workflow` if CI will run) and copy the token immediately

2) Configure Git locally (temporary method)
- In PowerShell (do not commit this):
  git remote set-url origin https://<YOUR_TOKEN>@github.com/YOUR_ORG/WebsiteFileDownloader.git
- Now you can push:
  git checkout -b feature/my-branch
  git add .
  git commit -m "Your message"
  git push origin feature/my-branch

3) Merge to main (if you want to do it directly)
- Ensure you are on `main` and it's up to date:
  git checkout main
  git pull origin main
- Merge:
  git merge --no-ff feature/my-branch -m "Merge feature: include Playwright browsers"
  git push origin main

Notes & Safety
- Embedding the token in the remote URL is convenient but risky; avoid saving tokens in plaintext files.
- Use Git Credential Manager where possible; it prompts you interactively.
- If you prefer, create a pull request rather than merging directly; this is the safer, review-friendly workflow.

If you want me to push and/or merge the branch for you, I can do that if you provide a PAT or enable a runner with access — tell me which option you prefer and I'll guide you through supplying the token securely.