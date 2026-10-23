# QuickMart Signal

A weekly grocery-delivery market brief for strategy and operations analysts, with every number traced to its source.
It is a Streamlit interface over the QuickMart data pipeline (Assignments 3–4).

- `app.py`: the interface
- `signal_core.py`: the data quality gate and the analysis. All numbers are calculated in code.
- `data/quickmart_dataset.csv`: the verified dataset (232 records from 3 sources, collected Oct 14, 2026)
- `test_files/`: files for trying the error states: a dataset missing a source, and a non-CSV file

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud (about 10 minutes)
1. Sign in to github.com and create a **new public repository**, for example `quickmart-signal`.
2. In the repository, click **Add file → Upload files**. Drag in everything in this folder **except** `shots/`:
   `app.py`, `signal_core.py`, `requirements.txt`, `README.md`, `.gitignore`, and the `data/`, `test_files/` and `.streamlit/` folders.
   The `.streamlit` folder is hidden in File Explorer: turn on View → Show → Hidden items. Then click **Commit changes**.
3. Go to share.streamlit.io, sign in with GitHub, and click **Create app → Deploy a public app from GitHub**.
4. Choose your repository, branch `main`, main file `app.py`. Under *App URL*, pick a name such as `quickmart-signal`. Click **Deploy**.
5. Wait 2–3 minutes. Open the URL in a private or incognito window to confirm that it works without you being logged in.

No API keys or secrets are needed: the app runs entirely on the verified dataset.
