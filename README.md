# HVAC Psychrometric Calculator

A Streamlit web application for HVAC psychrometric calculations and visualization.

## Deployment Instructions

1. **Create a GitHub Repository**

   - Push all code to a new GitHub repository
   - Ensure the following structure:
     ```
     psychro_app/
     ├── streamlit_app.py
     ├── requirements.txt
     ├── runtime.txt
     ├── README.md
     ├── .streamlit/
     │   └── config.toml
     └── psychro_app/
         ├── core/
         ├── systems/
         └── utils/
     ```

2. **Deploy on Streamlit Cloud**

   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Select your repository
   - Select main branch
   - Set Main file path to: `streamlit_app.py`
   - Click "Deploy"

3. **Environment Variables**
   - No environment variables required for basic deployment

## Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   streamlit run streamlit_app.py
   ```

## Requirements

- Python 3.9+
- Dependencies listed in requirements.txt
