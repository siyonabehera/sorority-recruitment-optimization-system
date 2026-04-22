import streamlit as st
import gspread
import pandas as pd
import numpy as np
import networkx as nx
import re
import difflib
import io
import zipfile
import time
import random  # Added for randomized backoff jitter
from io import BytesIO
from math import radians
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import haversine_distances
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials
from google import genai
from google.genai import types
import json

# Injecting Custom Purple/Violet CSS Theme (All White Text)
st.markdown("""
<style>
    /* Main background changed to Deep Violet */
    .stApp {
        background-color: #1A0B2E; 
    }
    
    /* Force standard text, list items, and input labels to be white */
    .stApp p, .stApp label, .stApp li, .stApp div[data-testid="stMarkdownContainer"] {
        color: #FFFFFF !important;
    }

    /* Ensure links are white to match the prompt and bolded for visibility */
    .stApp a {
        color: #FFFFFF !important; 
        text-decoration: underline !important;
        font-weight: bold;
    }
    
    /* --- HEADER FIX --- */
    header[data-testid="stHeader"] {
        background-color: #1A0B2E !important; 
    }
    
    /* Force header icons and text to be white */
    header[data-testid="stHeader"] *, 
    header[data-testid="stHeader"] button,
    header[data-testid="stHeader"] span,
    header[data-testid="stHeader"] a {
        color: #FFFFFF !important;
    }
    /* ------------------------------------- */

    /* Make headers White */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
    }
    
    /* --- INPUT FIELD STYLING --- */
    /* Target text inputs, text areas, number inputs, and select boxes */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="select"] > div {
        background-color: #2B134D !important; /* Mid-dark purple container */
        border: 1px solid #472183 !important; /* Accent purple border */
        border-radius: 6px;
    }
    
    /* Ensure text TYPED inside the boxes is white */
    div[data-baseweb="input"] input, 
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="select"] span {
        color: #FFFFFF !important; 
        font-weight: 500;
    }

    /* Change border color to solid white when user clicks to type */
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border: 2px solid #FFFFFF !important; 
    }

    /* --- CRITICAL FIX: DISABLED/AUTOFILLED INPUT FIELDS --- */
    input:disabled, 
    input[disabled], 
    textarea:disabled, 
    textarea[disabled] {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 0.7 !important;
    }

    div[aria-disabled="true"], 
    div[aria-disabled="true"] span, 
    div[aria-disabled="true"] input {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 0.7 !important;
    }

    div[aria-disabled="true"] > div,
    div[aria-disabled="true"] {
        background-color: #2B134D !important; 
    }
    /* ------------------------------------------------------- */

    /* --- NEW FIX: DROPDOWN MENU OPTIONS --- */
    /* Target the floating listbox and its options directly by their ARIA roles */
    ul[role="listbox"] {
        background-color: #2B134D !important; 
    }
    
    /* Target the individual options inside the dropdown */
    li[role="option"], 
    li[role="option"] span {
        color: #FFFFFF !important; 
        background-color: transparent !important;
    }
    
    /* Hover effect so users can see what they are selecting */
    li[role="option"]:hover, 
    li[role="option"][aria-selected="true"] {
        background-color: #472183 !important; 
        color: #FFFFFF !important; 
    }
    /* ------------------------------------- */

    /* --- BUTTON STYLING --- */
    .stButton>button {
        background-color: #472183; /* Accent purple */
        color: #FFFFFF !important;
        border-radius: 6px;
        border: 2px solid #FFFFFF; 
        padding: 10px 24px;
        font-weight: bold;
    }
    
    .stButton>button p, .stButton>button span {
        color: #FFFFFF !important; 
    }
    
    .stButton>button:hover, .stButton>button:focus {
        background-color: #2B134D;
        border: 2px solid #FFFFFF;
        box-shadow: 0px 4px 6px rgba(255,255,255,0.2); 
        transform: translateY(-1px); 
    }
    
    /* --- ALERT BOXES (Success, Error, Info, Warning) --- */
    div[data-testid="stAlert"] {
        background-color: #2B134D !important; 
        border: 1px solid #472183 !important;
        border-left: 6px solid #FFFFFF !important; 
        border-radius: 6px;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.2); 
    }
    
    div[data-testid="stAlert"] p, div[data-testid="stAlert"] span {
        color: #FFFFFF !important; 
        font-weight: 600; 
    }

    /* --- TOAST POP-UPS (Bottom right notifications) --- */
    div[data-testid="stToast"] {
        background-color: #2B134D !important;
        border: 2px solid #472183 !important;
        border-radius: 8px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
    }
    
    div[data-testid="stToast"] p, div[data-testid="stToast"] span {
        color: #FFFFFF !important; 
    }

    /* --- FORM CONTAINER --- */
    div[data-testid="stForm"] {
        background-color: #2B134D;
        border: 1px solid #472183; 
        border-radius: 8px; 
        padding: 20px; 
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
    }
    
    /* --- HIDE DEFAULT STREAMLIT FOOTER --- */
    footer {
        visibility: hidden;
    }
</style>
""", unsafe_allow_html=True)



# --- CONFIGURATION ---
SHEET_NAME = "OverallMatchingInformation"
ADMIN_PASSWORD = "password"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- AUTHENTICATION & CONNECTION ---
@st.cache_resource
def get_gspread_client():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Ensure your secrets are configured in .streamlit/secrets.toml
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ API Connection Error: {e}")
        return None

@st.cache_data
def load_city_database():
    # Global cities database
    url = "https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/master/csv/cities.csv"
    try:
        # Load the CSV
        ref_df = pd.read_csv(url, low_memory=False)
        
        # Drop rows that are missing the necessary matching data
        ref_df = ref_df.dropna(subset=['name', 'state_code', 'latitude', 'longitude'])
        
        # Construct the MATCH_KEY to match your form's "City, State" format
        ref_df['MATCH_KEY'] = (ref_df['name'].astype(str) + ", " + ref_df['state_code'].astype(str)).str.upper()
        
        # Drop duplicates to prevent dictionary key collisions
        ref_df = ref_df.drop_duplicates(subset=['MATCH_KEY'], keep='first')
        
        # Return the dictionary and the list of keys
        return {
            key: [lat, lon]
            for key, lat, lon in zip(ref_df['MATCH_KEY'], ref_df['latitude'], ref_df['longitude'])
        }, list(ref_df['MATCH_KEY'])
        
    except Exception as e:
        st.error(f"Failed to load global city database: {e}")
        return {}, []

# --- HELPERS WITH RETRY & CACHING ---

# 1. Cache the connection object
@st.cache_resource
def get_gc():
    if "gcp_service_account" not in st.secrets:
        st.error("Missing 'gcp_service_account' in Streamlit secrets.")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(creds_dict, scopes=SCOPES)

# 2. ROBUST WRITE WRAPPER (Prevents Quota Hits)
def robust_api_write(func, *args, **kwargs):
    """
    Executes a Google API write function with exponential backoff.
    Retries on 429 (Too Many Requests) or 500 (Server Error).
    """
    max_retries = 7
    for n in range(max_retries):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            # Check for Rate Limit (429) or Server Error (5xx)
            if hasattr(e, 'response') and (e.response.status_code == 429 or e.response.status_code >= 500):
                # Exponential backoff with jitter: 2s, 4s, 8s... + random ms
                sleep_time = (2 ** n) + random.uniform(0.5, 1.5)
                # Log to console or toast UI (optional)
                print(f"API Limit Hit. Retrying in {sleep_time:.2f}s...") 
                time.sleep(sleep_time)
            elif "429" in str(e) or "Quota exceeded" in str(e): # Fallback text check
                sleep_time = (2 ** n) + random.uniform(0.5, 1.5)
                time.sleep(sleep_time)
            else:
                raise e # Raise other errors (e.g., 403 Permission denied) immediately
        except Exception as e:
            raise e
    raise APIError("Max retries exceeded for Google Sheets API write operation.")

# --- NEW FUNCTION: SAFE WORKSHEET UPDATE ---
def update_worksheet_data(worksheet_title, df):
    """
    Safely updates an existing worksheet with a dataframe.
    Unlike clear(), this preserves existing cell colors, formatting, and data validation!
    """
    try:
        gc = get_gc()
        sh = gc.open(SHEET_NAME)
        ws = robust_api_write(sh.worksheet, worksheet_title)
        
        # Prepare Data: Handle NaNs and convert everything to strings for safe JSON transport
        df_clean = df.fillna("").astype(str)
        data_to_write = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # Update the sheet starting at A1. 
        robust_api_write(ws.update, values=data_to_write, range_name="A1")
        return True
    except Exception as e:
        print(f"Failed to update {worksheet_title}: {e}")
        return False

# 3. Smart Read with Retry (Existing logic preserved/cleaned)
def smart_read_sheet(sheet_object):
    for n in range(5): 
        try:
            return sheet_object.get_all_values()
        except APIError as e:
            if "429" in str(e) or "Quota" in str(e):
                time.sleep((2 ** n) + 1)
            else:
                raise e
    return []

# 4. Cache the data fetching
@st.cache_data(ttl=600)
def get_data(worksheet_name):
    try:
        gc = get_gc()
        sheet = gc.open(SHEET_NAME).worksheet(worksheet_name)
        data = smart_read_sheet(sheet)
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        if worksheet_name != "PNM Information": pass 
        return pd.DataFrame()

# 5. Cache the bulk loader
@st.cache_data(ttl=600)
def load_google_sheet_data(sheet_name):
    try:
        gc = get_gc()
        sh = gc.open(sheet_name)
        def get_df(ws_name):
            try:
                ws = sh.worksheet(ws_name)
                data = smart_read_sheet(ws)
                if not data: return pd.DataFrame()
                df = pd.DataFrame(data[1:], columns=data[0])
                return df
            except (gspread.WorksheetNotFound, Exception):
                return pd.DataFrame()

        bump_teams = get_df("Bump Teams")
        party_excuses = get_df("Party Excuses")
        pnm_info = get_df("PNM Information")
        mem_info = get_df("Member Information")
        prior_conn = get_df("Prior Connections")
        return bump_teams, party_excuses, pnm_info, mem_info, prior_conn
    except Exception as e:
        st.error(f"An error occurred connecting to Google Sheets: {e}")
        return None, None, None, None, None

def update_roster(names_list):
    try:
        gc = get_gc()
        ws = gc.open(SHEET_NAME).worksheet("Settings")
        # Use robust wrapper
        robust_api_write(ws.batch_clear, ["D2:D1000"])
        
        names_list.sort()
        formatted = [[n] for n in names_list if n.strip()]
        if formatted: 
            robust_api_write(ws.update, range_name='D2', values=formatted)
        return True
    except: return False

def update_visible_parties(parties_list):
    """
    Updates the list of parties that are visible/published to members in the Settings sheet.
    Uses Column E in the Settings tab.
    """
    try:
        gc = get_gc()
        ws = gc.open(SHEET_NAME).worksheet("Settings")
        # Use robust wrapper to clear old settings in Col E
        robust_api_write(ws.batch_clear, ["E2:E100"])
        
        parties_list.sort()
        # Format as list of lists for GSpread: [[1], [2], ...]
        formatted = [[str(p)] for p in parties_list]
        if formatted: 
            robust_api_write(ws.update, range_name='E2', values=formatted)
        return True
    except Exception as e:
        print(f"Error updating visible parties: {e}")
        return False

def update_team_ranking(team_id, new_ranking):
    try:
        gc = get_gc()
        sheet = gc.open(SHEET_NAME).worksheet("Bump Teams")
        cell = sheet.find(str(team_id), in_column=5)
        if cell:
            # Use robust wrapper
            robust_api_write(sheet.update_cell, cell.row, 6, new_ranking)
            get_data.clear()
            load_google_sheet_data.clear()
            return True
        return False
    except: return False

def batch_update_pnm_rankings(rankings_map):
    try:
        gc = get_gc()
        sheet = gc.open(SHEET_NAME).worksheet("PNM Information")
        all_values = smart_read_sheet(sheet)
        if not all_values: return 0
        headers = [h.lower().strip() for h in all_values[0]]
        try: id_idx = next(i for i, h in enumerate(headers) if 'pnm id' in h or 'id' == h)
        except: id_idx = 23
        try: rank_idx = next(i for i, h in enumerate(headers) if 'recruit rank' in h or 'average' in h)
        except: rank_idx = 24

        updates_count = 0
        for i in range(1, len(all_values)):
            row = all_values[i]
            if len(row) <= id_idx: continue
            p_id = str(row[id_idx]).strip()
            if p_id in rankings_map:
                while len(row) <= rank_idx: row.append("")
                row[rank_idx] = str(rankings_map[p_id])
                updates_count += 1
        
        # Use robust wrapper for the bulk update
        robust_api_write(sheet.update, values=all_values, range_name="A1")
        
        get_data.clear()
        load_google_sheet_data.clear()
        return updates_count
    except Exception as e:
        st.error(f"Batch update failed: {e}")
        return 0

def batch_update_team_rankings(rankings_map):
    try:
        gc = get_gc()
        sheet = gc.open(SHEET_NAME).worksheet("Bump Teams")
        all_values = smart_read_sheet(sheet)
        if not all_values: return 0
        headers = [h.lower().strip() for h in all_values[0]]
        try: id_idx = next(i for i, h in enumerate(headers) if 'team id' in h or 'id' == h)
        except: id_idx = 4
        try: rank_idx = next(i for i, h in enumerate(headers) if 'ranking' in h or 'rank' in h)
        except: rank_idx = 5

        updates_count = 0
        for i in range(1, len(all_values)):
            row = all_values[i]
            if len(row) <= id_idx: continue
            t_id = str(row[id_idx]).strip()
            if t_id in rankings_map:
                while len(row) <= rank_idx: row.append("")
                row[rank_idx] = str(rankings_map[t_id])
                updates_count += 1
        
        # Use robust wrapper for the bulk update
        robust_api_write(sheet.update, values=all_values, range_name="A1")
        
        get_data.clear()
        load_google_sheet_data.clear()
        return updates_count
    except Exception as e:
        st.error(f"Batch update failed: {e}")
        return 0

def get_max_party_count():
    try:
        df_party = get_data("Party Information")
        if df_party.empty: return 4
        party_col = next((c for c in df_party.columns if c.lower() == 'party'), None)
        if party_col:
            max_val = pd.to_numeric(df_party[party_col], errors='coerce').max()
            if pd.notna(max_val): return int(max_val)
        return 4
    except Exception: return 4

def auto_adjust_columns(writer, sheet_name, df):
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns):
        # Fallback width if the dataframe is empty
        if df.empty:
            max_len = len(str(col)) + 2
        else:
            # Use pandas-native .str.len() instead of standard Python map(len)
            max_data_len = df[col].astype(str).str.len().max()
            
            # Handle edge cases where the column might be entirely NaN/Null
            if pd.isna(max_data_len):
                max_data_len = 0
                
            max_len = max(int(max_data_len), len(str(col))) + 2
            
        worksheet.set_column(idx, idx, max_len)

# --- REGENERATION HELPER FOR TAB 8 ---
def regenerate_zip_from_changes():
    if not st.session_state.match_results or "preview_data" not in st.session_state.match_results: return
    data_map = st.session_state.match_results["preview_data"]
    zip_buffer = BytesIO()
    individual_party_files = []
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for party, df_rot_flow in data_map.items():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_rot_flow.to_excel(writer, sheet_name="Final_Matches_Edited", index=False)
                auto_adjust_columns(writer, "Final_Matches_Edited", df_rot_flow)
            file_content = output.getvalue()
            file_name_x = f"Party_{party}_Match_Analysis_Edited.xlsx"
            zf.writestr(file_name_x, file_content)
            individual_party_files.append((f"Party {party} (Edited)", file_name_x, file_content))
    st.session_state.match_results["zip_data"] = zip_buffer.getvalue()
    st.session_state.match_results["individual_files"] = individual_party_files

# --- NEW FUNCTION: SAVE TO GOOGLE SHEET (WITH RATE LIMIT PROTECTION) ---
def save_party_to_gsheet(party_num, df, specific_title=None):
    """
    Writes the given dataframe to a tab.
    Includes Robust Rate Limiting via robust_api_write.
    """
    try:
        gc = get_gc()
        sh = gc.open(SHEET_NAME)
        
        if specific_title:
            ws_title = specific_title
        else:
            ws_title = f"Party {party_num} Final Matches"
        
        # Check if worksheet exists, create if not
        try:
            # Try to open existing
            ws = robust_api_write(sh.worksheet, ws_title)
            # Clear it
            robust_api_write(ws.clear) 
        except WorksheetNotFound:
            # Create new if not found
            ws = robust_api_write(sh.add_worksheet, title=ws_title, rows=100, cols=20)
            
        # Prepare Data: Handle NaNs (convert to empty string) and timestamps
        df_clean = df.fillna("").astype(str)
        
        # GSpread requires a list of lists, including the header
        data_to_write = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # Write to sheet using robust wrapper
        robust_api_write(ws.update, values=data_to_write, range_name="A1")
        return True
    except Exception as e:
        st.error(f"Failed to save to Google Sheet: {e}")
        return False

# --- NEW FUNCTION: DELETE OLD MATCHING SHEETS ---
def delete_old_matching_sheets():
    """
    Deletes previously generated matching sheets to ensure a clean slate.
    Targets sheets starting with "Party " that contain matching keywords.
    """
    try:
        gc = get_gc()
        sh = gc.open(SHEET_NAME)
        worksheets = sh.worksheets()
        
        for ws in worksheets:
            title = ws.title.strip()
            # Deletion Criteria:
            # 1. Starts with "Party "
            # 2. Second part is a number (e.g., "Party 1")
            # 3. Contains "Matches" or "Flow" (output keywords)
            # This protects "Party Information" and "Party Excuses" from being deleted.
            parts = title.split()
            if len(parts) >= 2 and parts[0] == "Party" and parts[1].isdigit():
                if any(k in title for k in ["Matches", "Flow", "Round", "Final"]):
                    try:
                        robust_api_write(sh.del_worksheet, ws)
                        time.sleep(0.5) # Throttle to respect API limits
                    except Exception as e:
                        print(f"Failed to delete {title}: {e}")
    except Exception as e:
        st.warning(f"Note: Could not clear some previous sheets (Permissions or API limit): {e}")

# --- MATCHING ALGORITHM HELPERS ---
def get_coords_offline(hometown_str, city_coords_map, all_city_keys):
    if not isinstance(hometown_str, str): return None, None
    key = hometown_str.strip().upper()
    if key in city_coords_map: return city_coords_map[key]
    matches = difflib.get_close_matches(key, all_city_keys, n=1, cutoff=0.8)
    if matches: return city_coords_map[matches[0]]
    return None, None

def extract_terms(row, cols):
    text_parts = [str(row.get(c, '')).lower() for c in cols]
    combined = ", ".join([p for p in text_parts if p != 'nan' and p.strip() != ''])
    return [t.strip() for t in combined.split(',') if t.strip()]

def get_year_tag(year_val):
    valid_years = ["Freshman", "Sophomore", "Junior", "Senior"]
    if pd.isna(year_val): return None
    raw = str(year_val).strip()
    matches = difflib.get_close_matches(raw, valid_years, n=1, cutoff=0.6)
    return matches[0] if matches else raw.title()

# --- MAIN PAGE ---
st.set_page_config(page_title="Recruitment Admin Dashboard", layout="wide")
st.title("Sorority Recruitment Administration Dashboard")

if "match_results" not in st.session_state: st.session_state.match_results = None
if "authenticated" not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter Admin Password:", type="password")
    if pwd == ADMIN_PASSWORD:
        st.session_state.authenticated = True
        st.rerun()
else:
    st.success("Logged in as Admin")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Settings & Roster", "Member Information", "PNM Information and Rankings", 
        "View Bump Teams", "View Excuses", "View Prior Connections", "Run Matching",
        "Preview Matches and Edit" 
    ])

    # --- TAB 1: SETTINGS ---
    with tab1:
        st.header("Event Configuration")
        detected_party_count = get_max_party_count()
        st.info(f"**Party Count:** {detected_party_count} (Detected automatically from 'Party Information' sheet)")
        st.divider()
        st.header("Roster Management")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.subheader("Option A: Sync from Sheet")
            st.info("Pull names directly from the 'Member Information' tab.")
            if st.button("Sync Roster from 'Member Information'"):
                st.cache_data.clear() 
                df_source = get_data("Member Information")
                if not df_source.empty:
                    possible_cols = ["Full Name", "Name", "Member Name", "Member"]
                    found_col = None
                    for col in df_source.columns:
                        if any(c.lower() in col.lower() for c in possible_cols): found_col = col; break
                    if found_col:
                        names = df_source[found_col].astype(str).unique().tolist()
                        names = [n for n in names if n.strip()] 
                        if update_roster(names): st.success(f"✅ Successfully synced {len(names)} members!")
                        else: st.error("Failed to update Settings.")
                    else: st.error("Could not find name column.")
                else: st.error("'Member Information' sheet is empty.")
        with col_r2:
            st.subheader("Option B: Upload CSV")
            st.info("Upload a CSV file to strictly override the roster names.")
            file = st.file_uploader("Upload Member List (CSV)", type="csv")
            if file:
                try:
                    df_upload = pd.read_csv(file)
                    new_names = []
                    name_col = next((c for c in df_upload.columns if "name" in c.lower()), None)
                    if name_col: new_names = df_upload[name_col].astype(str).tolist()
                    else: new_names = df_upload.iloc[:, 0].astype(str).tolist() if not df_upload.empty else []
                    new_names = [n for n in new_names if n.lower() != 'nan' and n.strip()]
                    if new_names:
                        st.success(f"Found {len(new_names)} names in CSV.")
                        with st.expander("Preview Extracted Names (Click to View)"):
                            st.dataframe(pd.DataFrame(new_names, columns=["Names to Import"]), height=200, use_container_width=True)
                        if st.button("Override Roster with CSV"):
                            if update_roster(new_names): st.success("✅ Roster overwritten!"); st.toast("Roster Overwritten!")
                            else: st.error("Failed to update settings.")
                    else: st.warning("No valid names found.")
                except Exception as e: st.error(f"Error reading CSV: {e}")

    # --- TAB 2: MEMBER INFORMATION ---
    with tab2:
        st.header("Member Information Database")
        if st.button("Refresh Member Data"): 
            st.cache_data.clear()
            st.rerun()
        df_members = get_data("Member Information")
        if not df_members.empty:
            search_mem = st.text_input("Search Members:")
            if search_mem:
                mask = df_members.apply(lambda x: x.astype(str).str.contains(search_mem, case=False).any(), axis=1)
                display_df = df_members[mask]
            else: display_df = df_members
            st.metric("Total Members", len(display_df))
            st.dataframe(display_df, use_container_width=True)
        else: st.info("No member information found.")

    # --- TAB 3: PNM RANKINGS ---
    with tab3:
        st.header("PNM Ranking Management")
        if st.button("Refresh PNM & Ranking Data"):
            st.cache_data.clear()
            st.rerun()
        df_votes = get_data("PNM Rankings")
        df_pnms_master = get_data("PNM Information") 
        id_col_votes = None
        if not df_votes.empty:
            id_col_votes = next((c for c in df_votes.columns if 'pnm id' in c.lower() or 'id' == c.lower()), None)

        if not df_votes.empty and id_col_votes:
            st.markdown("### Ranking Validation Check")
            st.info("Set the minimum required rankings per PNM below.")
            c_val1, c_val2 = st.columns([1, 2])
            with c_val1:
                min_rankings_req = st.number_input("Minimum Rankings Required", min_value=1, value=3, step=1)
            
            master_id_col = next((c for c in df_pnms_master.columns if 'pnm id' in c.lower() or 'id' == c.lower()), None)
            master_name_col = next((c for c in df_pnms_master.columns if 'pnm name' in c.lower() or 'full name' in c.lower()), None)
            
            if not df_pnms_master.empty and master_id_col:
                vote_counts = df_votes[id_col_votes].astype(str).str.strip().value_counts().reset_index()
                vote_counts.columns = ['PNM ID', 'Vote Count']
                validation_df = df_pnms_master[[master_id_col]].copy()
                validation_df.columns = ['PNM ID']
                if master_name_col: validation_df['Name'] = df_pnms_master[master_name_col]
                else: validation_df['Name'] = "Unknown"
                validation_df['PNM ID'] = validation_df['PNM ID'].astype(str).str.strip()
                validation_df = validation_df.merge(vote_counts, on='PNM ID', how='left').fillna(0)
                validation_df['Vote Count'] = validation_df['Vote Count'].astype(int)
                failed_pnms = validation_df[validation_df['Vote Count'] < min_rankings_req]
                if not failed_pnms.empty:
                    st.error(f"{len(failed_pnms)} PNM(s) have fewer than {min_rankings_req} rankings!")
                    st.dataframe(failed_pnms.sort_values(by='Vote Count'), use_container_width=True, hide_index=True)
                else:
                    st.success(f"All {len(validation_df)} PNMs meet the minimum ranking requirement ({min_rankings_req}).")
            else:
                st.warning("Could not load PNM Master list for validation.")
            st.divider()

            try:
                df_votes['Score'] = pd.to_numeric(df_votes['Score'], errors='coerce')
                if id_col_votes and 'Score' in df_votes.columns:
                    group_cols = [id_col_votes]
                    name_col_votes = next((c for c in df_votes.columns if 'pnm name' in c.lower()), None)
                    if name_col_votes: group_cols.append(name_col_votes)
                    avg_df = df_votes.groupby(group_cols)['Score'].mean().reset_index()
                    avg_df.rename(columns={'Score': 'Calculated Average'}, inplace=True)
                    avg_df = avg_df.sort_values(by='Calculated Average', ascending=False)
                    st.subheader("Sync Rankings")
                    if st.button("Sync Rankings to PNM Sheet"):
                        with st.spinner("Syncing..."):
                            rankings_map = {str(row[id_col_votes]).strip(): round(row['Calculated Average'], 2) for idx, row in avg_df.iterrows()}
                            count = batch_update_pnm_rankings(rankings_map)
                        st.success(f"✅ Auto-synced {count} PNM rankings!")
                    st.divider()
                    st.subheader("Raw Ranking Data")
                    rank_search = st.text_input("Search Raw Rankings:", key="raw_rank_search")
                    if rank_search:
                        display_votes = df_votes[df_votes.astype(str).apply(lambda x: x.str.contains(rank_search, case=False).any(), axis=1)]
                    else:
                        display_votes = df_votes
                    st.dataframe(display_votes, use_container_width=True)
                else: st.error("Missing 'PNM ID' or 'Score' columns in Ranking Sheet.")
            except Exception as e: st.error(f"Error processing rankings: {e}")
        else: st.info("No votes found in 'PNM Rankings' sheet yet (or ID column missing).")
        st.divider()
        st.subheader("Current PNM Database")
        if not df_pnms_master.empty:
            pnm_search = st.text_input("Search PNM Database:")
            display_pnm = df_pnms_master[df_pnms_master.astype(str).apply(lambda x: x.str.contains(pnm_search, case=False).any(), axis=1)] if pnm_search else df_pnms_master
            st.dataframe(display_pnm, use_container_width=True)
        else: st.info("No PNM data found.")  

    # --- TAB 4: VIEW BUMP TEAMS ---
    with tab4:
        st.header("Bump Team Management")
        if st.button("Refresh Bump Teams"):
            st.cache_data.clear()
            st.rerun()
        df_teams = get_data("Bump Teams")
        if not df_teams.empty:
            id_col = next((c for c in df_teams.columns if 'team id' in c.lower() or 'id' in c.lower()), df_teams.columns[4] if len(df_teams.columns)>4 else None)
            creator_col = next((c for c in df_teams.columns if 'creator' in c.lower()), df_teams.columns[1] if len(df_teams.columns)>1 else None)
            partners_col = next((c for c in df_teams.columns if 'partner' in c.lower()), df_teams.columns[2] if len(df_teams.columns)>2 else None)
            rank_col = next((c for c in df_teams.columns if 'rank' in c.lower()), None)
            if id_col and creator_col:
                df_teams['display_label'] = df_teams.apply(lambda x: f"Team {x[id_col]} | {x[creator_col]}, {x.get(partners_col, '')}", axis=1)
                t1, t2 = st.tabs(["Single Team Recruiter Ranking Update", "Bulk Team Recruiter Ranking Upload (CSV)"])
                with t1:
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        sel_label = st.selectbox("Select Team to Rank:", df_teams['display_label'].tolist())
                        sel_id = df_teams[df_teams['display_label'] == sel_label][id_col].values[0]
                    with c2:
                        cur_rank = df_teams[df_teams[id_col] == sel_id][rank_col].values[0] if rank_col else 1
                        try: init_val = int(cur_rank)
                        except: init_val = 1
                        new_rank = st.number_input(f"Assign Rank:", min_value=1, value=init_val, key="team_rank_input")
                    with c3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Save Team Rank"):
                            if update_team_ranking(sel_id, new_rank): st.success(f"Rank {new_rank} assigned!"); st.rerun()
                with t2:
                    st.info('Upload a CSV with columns: "Team ID" (or "Creator Name") and "Ranking".')
                    team_csv = st.file_uploader("Upload Rankings CSV", type=["csv"], key="team_rank_upload")
                    if team_csv and st.button("Process Bulk Update"):
                        try:
                            df_b = pd.read_csv(team_csv)
                            df_b.columns = df_b.columns.str.strip().str.lower()
                            b_id = next((c for c in df_b.columns if 'id' in c), None)
                            b_name = next((c for c in df_b.columns if 'name' in c or 'creator' in c), None)
                            b_rank = next((c for c in df_b.columns if 'rank' in c), None)
                            if b_rank and (b_id or b_name):
                                bulk_map = {}
                                name_map = dict(zip(df_teams[creator_col].astype(str).str.strip().str.lower(), df_teams[id_col].astype(str))) if b_name else {}
                                for _, r in df_b.iterrows():
                                    rv = r[b_rank]
                                    tid = None
                                    if b_id and pd.notna(r[b_id]): tid = str(int(r[b_id])) if str(r[b_id]).replace('.','').isdigit() else str(r[b_id])
                                    elif b_name and pd.notna(r[b_name]): tid = name_map.get(str(r[b_name]).strip().lower())
                                    if tid: bulk_map[tid] = rv
                                if bulk_map:
                                    cnt = batch_update_team_rankings(bulk_map)
                                    st.success(f"✅ Updated {cnt} teams!"); st.rerun()
                                else: st.warning("No valid teams found.")
                            else: st.error("CSV missing required columns.")
                        except Exception as e: st.error(f"Error: {e}")
            st.divider()
            st.subheader("Current Bump Teams List")
            team_search = st.text_input("Search Bump Teams:", key="bump_team_search")
            if team_search:
                display_teams = df_teams[df_teams.astype(str).apply(lambda x: x.str.contains(team_search, case=False).any(), axis=1)]
            else:
                display_teams = df_teams
            st.dataframe(display_teams.drop(columns=['display_label'], errors='ignore'), use_container_width=True)
        else: st.info("No bump teams found yet.")
            
    # --- TAB 5 & 6: EXCUSES & CONNECTIONS ---
    with tab5:
        st.header("Member Party Excuses")
        if st.button("Refresh Excuses"): 
            st.cache_data.clear()
            st.rerun()
        df_ex = get_data("Party Excuses")
        if not df_ex.empty:
            excuse_search = st.text_input("Search Excuses:", key="excuse_search_input")
            if excuse_search:
                display_ex = df_ex[df_ex.astype(str).apply(lambda x: x.str.contains(excuse_search, case=False).any(), axis=1)]
            else: display_ex = df_ex
            st.dataframe(display_ex, use_container_width=True)
        else: st.info("No excuses found.")

    with tab6:
        st.header("Prior Member - PNM Connections")
        if st.button("Refresh Connections"): 
            st.cache_data.clear()
            st.rerun()
        df_conn = get_data("Prior Connections")
        if not df_conn.empty:
            conn_search = st.text_input("Search Prior Connections:", key="conn_search_input")
            if conn_search:
                display_conn = df_conn[df_conn.astype(str).apply(lambda x: x.str.contains(conn_search, case=False).any(), axis=1)]
            else: display_conn = df_conn
            st.dataframe(display_conn, use_container_width=True)
        else: st.info("No prior connections found.")

    # --- TAB 7: RUN MATCHING ---
    with tab7:
        st.header("Run Matching Algorithm")
        st.subheader("Matching Algorithm Settings")
        num_parties = get_max_party_count() 
        st.info(f"**Total Parties:** {num_parties} (Detected from 'Party Information' sheet)")

        # --- Party Selection for Visibility ---
        party_opts = list(range(1, num_parties + 1))
        
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            selected_parties_to_show = st.multiselect(
                "Select Parties to Publish to Members:", 
                options=party_opts,
                format_func=lambda x: f"Party {x}", 
                default=[] 
            )
            st.caption("**Note:** Updating this list and clicking 'Save' allows you to change which parties members can see immediately, without needing to re-run the entire matching algorithm.")

        with col_p2:
            st.markdown("<br>", unsafe_allow_html=True) # Spacer
            if st.button("Save Published Parties"):
                with st.spinner("Saving settings..."):
                    if update_visible_parties(selected_parties_to_show):
                        st.success("Saved!")
                    else:
                        st.error("Error saving.")

        matches_per_team = st.number_input("Matches per Bump Team (Capacity)", min_value=1, value=2)
        num_rounds = st.number_input("Bumps per Party", min_value=1, value=4)
        bump_order_set = st.radio("Is Bump Order Set?", ("Yes", "No"), horizontal=True)
        is_bump_order_set = "y" if bump_order_set == "Yes" else "n"
        st.divider()
        preprocess_button = st.button("1. Preprocess Attributes", type="secondary", use_container_width=True)
        st.divider()
        st.subheader("Upload PNM Party Assignments")
        party_assignment_file = st.file_uploader("Upload CSV containing 'PNM ID', 'PNM Name', and 'Party'", type=["csv"])
        if party_assignment_file:
            try:
                df_preview = pd.read_csv(party_assignment_file)
                party_assignment_file.seek(0)
                with st.expander("Preview Uploaded Data (Click to Expand)"):
                    st.write(f"**Rows found:** {len(df_preview)}")
                    st.dataframe(df_preview.head(), use_container_width=True)
            except Exception as e: st.error(f"Error generating preview: {e}")
        
        run_button = st.button("2. Run Matching Algorithm", type="primary", use_container_width=True)
        
        # ==========================================
        # BUTTON 1: PREPROCESS ATTRIBUTES
        # ==========================================
        if preprocess_button:
            # We use an empty container so we can update text dynamically without making the page scroll
            status_container = st.empty()
            
            with st.spinner("Initializing data..."):
                bump_teams, party_excuses, pnm_intial_interest, member_interest, member_pnm_no_match = load_google_sheet_data(SHEET_NAME)
                if any(df is None for df in [pnm_intial_interest, member_interest]): 
                    st.error("Failed to load required sheet data.")
                    st.stop()
                
                for df in [pnm_intial_interest, member_interest]: 
                    df.columns = df.columns.str.strip()
                
                city_coords_map, all_city_keys = load_city_database()

                # --- 1. STANDARDIZE COLUMNS ---
                pnm_col_map = {
                    'Enter your name:': 'Full Name',
                    'Enter your hometown in the form City, State:': 'Hometown',
                    'Enter your major or "Undecided":': 'Major',
                    'Enter your minor or leave blank:': 'Minor',
                    'Enter your high school involvement (sports, clubs etc.), separate each activity by a comma:': 'High School Involvement',
                    'Enter your college involvement (sports, clubs etc.), separate each activity by a comma:': 'College Involvement',
                    'Enter your hobbies and interests, separate each activity by a comma:': 'Hobbies',
                    'Pick your year in school:': 'Year'
                }
                pnm_clean = pnm_intial_interest.rename(columns=pnm_col_map)
                df_mem = member_interest.copy()

                # --- 2. LOCAL OFFLINE HELPER ---
                def get_coords_offline_local(hometown_str, coords_map, keys_list):
                    if not isinstance(hometown_str, str): return None, None
                    key = hometown_str.strip().upper()
                    if key in coords_map:
                        return coords_map[key][0], coords_map[key][1]
                    matches = difflib.get_close_matches(key, keys_list, n=1, cutoff=0.8)
                    if matches:
                        return coords_map[matches[0]][0], coords_map[matches[0]][1]
                    return None, None

                def get_coords_offline_local(hometown_str, coords_map, keys_list):
                    if not isinstance(hometown_str, str): return None, None
                    key = hometown_str.strip().upper()
                    if key in coords_map:
                        return coords_map[key][0], coords_map[key][1]
                    if "," in key:
                        city_part, state_part = key.split(",", 1)
                        state_code = state_part.strip()
                        narrowed_keys = [k for k in keys_list if k.endswith(f", {state_code}")]
                        
                        if narrowed_keys:
                            matches = difflib.get_close_matches(key, narrowed_keys, n=1, cutoff=0.8)
                            if matches:
                                return coords_map[matches[0]][0], coords_map[matches[0]][1]
                    return None, None

                # --- 3. GEO CLUSTERING ---
                status_container.info("Processing offline geographical clusters...")
                all_coords, geo_tracker = [], []
                for idx, row in df_mem.iterrows():
                    lat, lon = get_coords_offline_local(row.get('Hometown'), city_coords_map, all_city_keys)
                    if lat is not None:
                        all_coords.append([radians(lat), radians(lon)])
                        geo_tracker.append({'type': 'mem', 'id': row['Sorority ID'], 'hometown': row['Hometown']})

                for idx, row in pnm_clean.iterrows():
                    lat, lon = get_coords_offline_local(row.get('Hometown'), city_coords_map, all_city_keys)
                    if lat is not None:
                        all_coords.append([radians(lat), radians(lon)])
                        geo_tracker.append({'type': 'pnm', 'id': row['PNM ID'], 'hometown': row['Hometown']})

                mem_geo_tags, pnm_geo_tags = {}, {}
                if all_coords:
                    dist_matrix = haversine_distances(all_coords, all_coords) * 3958.8
                    geo_clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=30, metric='precomputed', linkage='single')
                    geo_labels = geo_clustering.fit_predict(dist_matrix)
                    
                    geo_groups = {}
                    for i, label in enumerate(geo_labels):
                        if label not in geo_groups: geo_groups[label] = []
                        geo_groups[label].append(geo_tracker[i]['hometown'])
                        
                    for i, label in enumerate(geo_labels):
                        group_name = geo_groups[label][0]
                        tracker = geo_tracker[i]
                        if tracker['type'] == 'mem': mem_geo_tags[tracker['id']] = group_name
                        else: pnm_geo_tags[tracker['id']] = group_name

                # --- 4. SEMANTIC EXTRACTION (GEMINI) ---
                try:
                    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
                    client_extract = genai.Client(api_key=GEMINI_API_KEY)
                except Exception as e:
                    st.error(f"Failed to initialize Gemini API. Have you set GEMINI_API_KEY in Streamlit secrets? Error: {e}")
                    st.stop()

                EXTRACTION_MODEL = "gemini-3.1-flash-lite-preview"
                EXTRACTION_BATCH_SIZE = 40
                EXTRACTION_RETRY_ATTEMPTS = 12
                EXTRACTION_RETRY_DELAY = 15
                MIN_SECONDS_PER_REQUEST = 6.5

                EXTRACTION_SYSTEM_PROMPT = """You are a recruitment matching assistant for a college sorority.
                Read each person's academic and personal profile and extract normalized semantic tags
                that will be used to match them with compatible people.
                EXISTING TAGS:
                {existing_tags}

                TAG RULES:
                - Lowercase with underscores (e.g. pre_med, greek_life, east_coast)
                - Normalize similar things to one tag: "club volleyball", "JV volleyball", "sand v-ball" → volleyball
                - Capture career intent: "wants to be a doctor", "pre-med" → healthcare_career
                - Capture shared background: "small town girl", "rural upbringing" → small_town_background
                - Capture meaningful values: "first gen student", "first generation college" → first_generation
                - Include: academic field, career direction, sports/athletics, hobbies, org involvement, background
                - IF AN EXISTING TAG FITS perfectly, you MUST use it rather than creating a new variation.
                - Only invent a new tag if the existing tags do not cover the person's profile.
                - Return 5–12 tags per person
                - BE CONSISTENT: if two people have similar profiles they MUST share tags — this is critical
                  for the matching algorithm to work correctly

                Return ONLY a JSON array of arrays, one inner array per person in the same order given.
                Example for 2 people: [["pre_med", "volleyball", "midwest"], ["business", "greek_life", "east_coast"]]
                No markdown fences, no explanation, just the JSON array."""

                def _build_profile_str(row: dict) -> str:
                    parts = []
                    for field in ['Major', 'Minor', 'High School Involvement', 'College Involvement', 'Hobbies']:
                        val = str(row.get(field, '')).strip()
                        if val and val.lower() not in ('nan', '', 'none'):
                            parts.append(f"{field}: {val}")
                    return "\n".join(parts) if parts else "No profile information provided."

                def _extract_attrs_batch(profiles: list, master_tags: set) -> list:
                    numbered = [f"Person {i+1}:\n{p}" for i, p in enumerate(profiles)]
                    # Format the prompt with the running list of tags
                    tags_str = ", ".join(sorted(master_tags)) if master_tags else "None yet. You are the first batch, establish a good baseline."
                    content = EXTRACTION_SYSTEM_PROMPT.format(existing_tags=tags_str) + "\n\n" + "\n\n".join(numbered)

                    for attempt in range(1, EXTRACTION_RETRY_ATTEMPTS + 1):
                        try:
                            response = client_extract.models.generate_content(
                                model=EXTRACTION_MODEL,
                                contents=content,
                                config=types.GenerateContentConfig(
                                    temperature=0.1,
                                    max_output_tokens=8192
                                )
                            )
                            raw = response.text.strip()
                            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
                            result = json.loads(raw)

                            while len(result) < len(profiles):
                                result.append([])
                            return [set(str(t).lower() for t in tags) for tags in result[:len(profiles)]]

                        except Exception as e:
                            err_str = str(e).lower()
                            if any(x in err_str for x in ["429", "503", "quota", "resourceexhausted", "unavailable"]):
                                wait = (2 ** attempt) + random.uniform(1, 5) + 10
                                status_container.warning(f"API Busy/Overloaded (Attempt {attempt}/{EXTRACTION_RETRY_ATTEMPTS}). Waiting {wait:.1f}s...")
                            else:
                                wait = EXTRACTION_RETRY_DELAY
                                status_container.warning(f"API/Parse Error: {e}. Waiting {wait}s...")

                            if attempt < EXTRACTION_RETRY_ATTEMPTS:
                                time.sleep(wait)
                            else:
                                status_container.error("Extraction failed for this batch — assigning empty tags.")
                                return [set() for _ in profiles]

                def process_dataframe_llm(df, id_col_name, entity_name, master_tags):
                    llm_attrs = {}
                    rows = df.to_dict('records')
                    total_batches = (len(rows) + EXTRACTION_BATCH_SIZE - 1) // EXTRACTION_BATCH_SIZE
                    progress_bar = st.progress(0)
                    
                    for batch_idx, batch_start in enumerate(range(0, len(rows), EXTRACTION_BATCH_SIZE)):
                        batch_start_time = time.time()
                        batch = rows[batch_start: batch_start + EXTRACTION_BATCH_SIZE]
                        profiles = [_build_profile_str(r) for r in batch]
                        end = min(batch_start + EXTRACTION_BATCH_SIZE, len(rows))
                        status_container.info(f"Extracting {entity_name} Semantic Tags via Gemini: {batch_start+1}–{end} of {len(rows)}...")
                        
                        tag_lists = _extract_attrs_batch(profiles, master_tags)
                        
                        for i, row in enumerate(batch):
                            extracted_tags = tag_lists[i]
                            llm_attrs[row[id_col_name]] = extracted_tags
                            master_tags.update(extracted_tags) 
                        
                        progress_bar.progress((batch_idx + 1) / total_batches)
                        elapsed = time.time() - batch_start_time
                        sleep_time = max(0.0, MIN_SECONDS_PER_REQUEST - elapsed)
                        if batch_start + EXTRACTION_BATCH_SIZE < len(rows):
                            time.sleep(sleep_time)
                    progress_bar.empty()
                    return llm_attrs

                shared_vocabulary = set()
                mem_llm_attrs = process_dataframe_llm(df_mem, 'Sorority ID', 'Members', shared_vocabulary)
                pnm_llm_attrs = process_dataframe_llm(pnm_clean, 'PNM ID', 'PNMs', shared_vocabulary)
                status_container.success("Geographical and Semantic Attribute extraction complete! Finalizing...")

                # --- 5. FINALIZE ATTRIBUTES ---
                def finalize_attributes_llm(df, id_col, geo_tags, llm_tags):
                    final_attrs = {row[id_col]: set() for _, row in df.iterrows()}
                    for idx, row in df.iterrows():
                        pid = row[id_col]
                        
                        # Add Class Year tag
                        yt = get_year_tag(row.get('Year'))
                        if yt: final_attrs[pid].add(yt)
                        
                        # Add Geo tag
                        if pid in geo_tags: final_attrs[pid].add(geo_tags[pid])
                            
                        # Add Gemini LLM tags
                        if pid in llm_tags: final_attrs[pid].update(llm_tags[pid])
                            
                    return df[id_col].map(lambda x: ", ".join(final_attrs.get(x, set())))

                # Append to original DataFrames
                member_interest['attributes_for_matching'] = finalize_attributes_llm(df_mem, 'Sorority ID', mem_geo_tags, mem_llm_attrs)
                pnm_intial_interest['attributes_for_matching'] = finalize_attributes_llm(pnm_clean, 'PNM ID', pnm_geo_tags, pnm_llm_attrs)
                
                # --- 6. WRITE BACK TO GOOGLE SHEETS ---
                with st.spinner("Writing finalized attributes back to Google Sheets..."):
                    try:
                        # Safely update the master tabs
                        mem_success = update_worksheet_data("Member Information", member_interest)
                        pnm_success = update_worksheet_data("PNM Information", pnm_intial_interest)
                        
                        if mem_success and pnm_success:
                            status_container.success("✅ Attributes successfully preprocessed and saved to Google Sheets!")
                            
                            # CRITICAL: Clear the data cache so that when the user clicks 
                            # "Run Matching Algorithm", the app pulls the fresh data containing the new columns!
                            get_data.clear()
                            load_google_sheet_data.clear()
                        else:
                            status_container.error("⚠️ There was an issue writing the data to the sheets. Check your console logs.")
                            
                    except Exception as e:
                        status_container.error(f"Error writing to Google Sheets: {e}")


        # ==========================================
        # BUTTON 2: RUN MATCHING ALGORITHM
        # ==========================================
        if run_button:
            if not party_assignment_file:
                st.error("❌ Please upload the PNM Party Assignments CSV to proceed.")
            else:
                with st.spinner("Saving Party Visibility Settings..."):
                    update_visible_parties(selected_parties_to_show)

                with st.spinner("Clearing previous matching results..."):
                    delete_old_matching_sheets()
                
                with st.spinner("Loading preprocessed attributes and processing matches..."):
                    bump_teams, party_excuses, pnm_intial_interest, member_interest, member_pnm_no_match = load_google_sheet_data(SHEET_NAME)
                    if any(df is None for df in [bump_teams, party_excuses, pnm_intial_interest, member_interest, member_pnm_no_match]): st.stop()
                    for df in [bump_teams, party_excuses, pnm_intial_interest, member_interest, member_pnm_no_match]: df.columns = df.columns.str.strip()
                    
                    # Verify Preprocessing was run
                    if 'attributes_for_matching' not in member_interest.columns or 'attributes_for_matching' not in pnm_intial_interest.columns:
                        st.error("❌ 'attributes_for_matching' column not found! Please run 'Preprocess Attributes' first.")
                        st.stop()

                    try:
                        assignments_df = pd.read_csv(party_assignment_file)
                        assignments_df.columns = assignments_df.columns.str.strip()
                        required_assignment_cols = ['PNM ID', 'Party']
                        if not all(col in assignments_df.columns for col in required_assignment_cols):
                            st.error(f"Uploaded CSV must contain columns: {required_assignment_cols}. Found: {list(assignments_df.columns)}")
                            st.stop()
                        pnm_intial_interest['PNM ID'] = pnm_intial_interest['PNM ID'].astype(str).str.strip()
                        assignments_df['PNM ID'] = assignments_df['PNM ID'].astype(str).str.strip()
                        pnm_intial_interest = pnm_intial_interest.merge(assignments_df[['PNM ID', 'Party']], on='PNM ID', how='inner')
                        if pnm_intial_interest.empty:
                            st.error("No matches found between the uploaded PNM Assignments and the PNM Information database. Check your PNM IDs.")
                            st.stop()
                        pnm_intial_interest['Party'] = pd.to_numeric(pnm_intial_interest['Party'], errors='coerce').fillna(0).astype(int)
                    except Exception as e:
                        st.error(f"Error reading or processing the Party Assignments CSV: {e}"); st.stop()

                    try:
                        all_ranks = pd.to_numeric(pnm_intial_interest['Average Recruit Rank'], errors='coerce')
                        min_obs = all_ranks.min()
                        if pd.isna(min_obs): min_obs = 1.0
                        all_ranks = all_ranks.fillna(min_obs)
                        global_max = all_ranks.max()
                        global_min = all_ranks.min()
                        if global_max == global_min: global_max += 1.0 
                        
                        all_team_ranks = pd.to_numeric(bump_teams['Ranking'], errors='coerce')
                        min_t_obs = all_team_ranks.min()
                        if pd.isna(min_t_obs): min_t_obs = 1.0
                        all_team_ranks = all_team_ranks.fillna(4.0)
                        t_global_max = all_team_ranks.max()
                        t_global_min = all_team_ranks.min()
                        if t_global_max == t_global_min: t_global_max += 1.0
                    except Exception as e:
                        st.error(f"Error calculating global ranking stats: {e}")
                        global_max, global_min = 5.0, 1.0 
                        t_global_max, t_global_min = 4.0, 1.0

                    zip_buffer = BytesIO()
                    party_excuses["Choose the party/parties you are unable to attend:"] = party_excuses["Choose the party/parties you are unable to attend:"].apply(
                        lambda x: [int(i) for i in re.findall(r'\d+', str(x))] if pd.notnull(x) else []
                    )
                    party_excuses = party_excuses.explode("Choose the party/parties you are unable to attend:")
                    member_pnm_no_match["PNM Name"] = member_pnm_no_match["PNM Name"].str.split(r',\s*', regex=True)
                    member_pnm_no_match = member_pnm_no_match.explode("PNM Name")
                    no_match_pairs = { (row["Member Name"], row["PNM Name"]) for row in member_pnm_no_match.to_dict('records') }
                    member_attr_cache = {
                        row['Sorority ID']: set(str(row.get('attributes_for_matching', '')).split(', '))
                        if row.get('attributes_for_matching') else set()
                        for row in member_interest.to_dict('records')
                    }
                    name_to_id_map = member_interest.set_index('Full Name')['Sorority ID'].to_dict()
                    all_member_traits = member_interest['attributes_for_matching'].str.split(', ').explode()
                    trait_freq = all_member_traits.value_counts()
                    trait_weights = (len(member_interest) / trait_freq).to_dict()
                    
                    def to_float(val, default=1.0):
                        try: return float(val)
                        except: return default
                    def to_int(val, default=4):
                        try: return int(val)
                        except: return default

                    individual_party_files = []
                    preview_results = {} 

                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for party in range(1, int(num_parties) + 1):
                            pnms_df = pnm_intial_interest[pnm_intial_interest['Party'] == party].copy()
                            if pnms_df.empty: continue
                            pnm_list = []
                            pnm_records = pnms_df.to_dict('records')
                            for i, row in enumerate(pnm_records):
                                p_attrs = set(str(row['attributes_for_matching']).split(', '))
                                p_rank_val = to_float(row.get("Average Recruit Rank", 1.0))
                                safe_rank = max(global_min, min(p_rank_val, global_max))
                                relative_strength = (safe_rank - global_min) / (global_max - global_min)
                                RANKING_WEIGHT = 3.0 
                                pnm_bonus = relative_strength * RANKING_WEIGHT
                                pnm_list.append({
                                    'idx': i, 'id': row['PNM ID'], 'name': row.get('PNM Name', row.get('Full Name')),
                                    'attrs': p_attrs, 'rank': p_rank_val, 'bonus': pnm_bonus, 'node_id': f"p_{i}"
                                })
                            party_excused_names = set(party_excuses[party_excuses["Choose the party/parties you are unable to attend:"] == party]["Member Name"])
                            team_list = []
                            broken_teams_list = []
                            for raw_idx, row in enumerate(bump_teams.to_dict('records')):
                                submitter = row["Creator Name"]
                                partners_str = str(row.get("Bump Partners", ""))
                                if partners_str.lower() == 'nan': partners = []
                                else: partners = [p.strip() for p in re.split(r'[,;]\s*', partners_str) if p.strip()]
                                current_members = [submitter] + partners
                                missing_members = [m for m in current_members if m in party_excused_names]
                                t_id = str(row.get("Team ID", row.get("ID", "Unknown"))) 
                                if missing_members:
                                    broken_teams_list.append({
                                        'id': t_id,
                                        'members': current_members, 
                                        'missing': missing_members
                                    })
                                else:
                                    t_rank_val = to_float(row.get("Ranking", t_global_max))
                                    safe_t_rank = max(t_global_min, min(t_rank_val, t_global_max))
                                    team_rel_strength = (t_global_max - safe_t_rank) / (t_global_max - t_global_min)
                                    TEAM_WEIGHT = 1.5 
                                    t_bonus = team_rel_strength * TEAM_WEIGHT
                                    team_list.append({
                                        't_idx': len(team_list), 'members': current_members, 'team_size': len(current_members),
                                        'member_ids': [name_to_id_map.get(m) for m in current_members],
                                        'joined_names': ", ".join(current_members), 'bonus': t_bonus,
                                        'node_id': f"t_{len(team_list)}", 'row_data': row
                                    })
                            total_capacity = len(team_list) * matches_per_team
                            if len(pnm_list) > total_capacity:
                                warning_msg = (f"**Party {party} Warning**: Not enough capacity! {len(pnm_list)} PNMs vs {total_capacity} Slots.\n\n")
                                if broken_teams_list:
                                    warning_msg += f"- **Excused Teams:** {len(broken_teams_list)} team(s) removed.\n\n"
                                    for item in broken_teams_list:
                                        all_mems = ", ".join(item['members'])
                                        missing_mems = ", ".join(item['missing'])
                                        warning_msg += f"  • **Team {item['id']}** (Members: {all_mems}) removed.\n"
                                        warning_msg += f"    *Reason:* **{missing_mems}** is excused from this party.\n"
                                else: 
                                    warning_msg += "No teams were removed due to excuses for this party.\n"

                                warning_msg += "\n"
                                
                                # --- MODIFIED: Detailed Conflict Reporting (With IDs) ---
                                pnm_name_to_id = {p['name']: p['id'] for p in pnm_list}
                                member_name_to_id = {}
                                active_team_members = set()
                                for t in team_list: 
                                    active_team_members.update(t['members'])
                                    for m_name, m_id in zip(t['members'], t['member_ids']):
                                        if m_name and m_id:
                                            member_name_to_id[m_name] = m_id

                                pnm_names_in_party = set(pnm_name_to_id.keys())
                                relevant_conflicts = []
                                
                                for (m_name, p_name) in no_match_pairs:
                                    if p_name in pnm_names_in_party and m_name in active_team_members:
                                        m_id = member_name_to_id.get(m_name, "Unknown ID")
                                        p_id = pnm_name_to_id.get(p_name, "Unknown ID")
                                        relevant_conflicts.append(f"Member **{m_name}** (ID: {m_id}) & PNM **{p_name}** (ID: {p_id})")
                                
                                if relevant_conflicts:
                                    warning_msg += f"- **Active No-Match Constraints:** {len(relevant_conflicts)} pair(s) found.\n\n"
                                    for conflict in relevant_conflicts:
                                        warning_msg += f"  • {conflict}\n"
                                else: 
                                    warning_msg += "No conflicts found between present PNMs and Members.\n"
                                # ---------------------------------------------------------
                                
                                st.warning(warning_msg)

                            potential_pairs = []
                            for p_data in pnm_list:
                                for t_data in team_list:
                                    if any((m, p_data['name']) in no_match_pairs for m in t_data['members']): continue
                                    score = 0
                                    reasons_list = []
                                    for m_id, m_name in zip(t_data['member_ids'], t_data['members']):
                                        if m_id is None: continue
                                        m_attrs = member_attr_cache.get(m_id, set())
                                        shared = p_data['attrs'].intersection(m_attrs)
                                        if shared:
                                            score += sum(trait_weights.get(t, 1.0) for t in shared)
                                            reasons_list.append(f"{p_data['name']} has {', '.join(shared)} with {m_name}.")
                                    total_score = score + t_data['bonus'] + p_data['bonus']
                                    final_cost = 1 / (1 + total_score)
                                    potential_pairs.append({
                                        'p_id': p_data['id'], 'p_name': p_data['name'], 'p_attrs': p_data['attrs'],
                                        't_idx': t_data['t_idx'], 'team_size': t_data['team_size'],
                                        'p_node': p_data['node_id'], 't_node': t_data['node_id'],
                                        'cost': final_cost, 'pnm_rank': p_data['rank'],
                                        'team_members': t_data['joined_names'],
                                        'reasons': " ".join(reasons_list) if reasons_list else "No specific match",
                                        'team_ranking': to_float(t_data['row_data'].get('Ranking', 4.0))
                                    })
                            potential_pairs.sort(key=lambda x: (x['cost'], -x['pnm_rank']))
                            matchable_pnm_ids = {p['p_id'] for p in potential_pairs}

                            global_flow_results = []
                            assignments_map_flow = {t['t_idx']: [] for t in team_list}
                            G = nx.DiGraph()
                            source, sink, no_match_node = 'source', 'sink', 'dummy_nomatch'
                            total_flow = len(pnm_list)
                            G.add_node(source, demand=-total_flow); G.add_node(sink, demand=total_flow); G.add_node(no_match_node)
                            for p in pnm_list: G.add_edge(source, p['node_id'], capacity=1, weight=0); G.add_edge(p['node_id'], no_match_node, capacity=1, weight=1000000)
                            for t in team_list: G.add_edge(t['node_id'], sink, capacity=matches_per_team, weight=0)
                            G.add_edge(no_match_node, sink, capacity=total_flow, weight=0)
                            for pair in potential_pairs: G.add_edge(pair['p_node'], pair['t_node'], capacity=1, weight=int(pair['cost'] * 10000))

                            try:
                                flow_dict = nx.min_cost_flow(G)
                                pair_lookup = {(p['p_node'], p['t_node']): p for p in potential_pairs}
                                pnm_ids_with_potential = {p['p_id'] for p in potential_pairs}
                                for p_data in pnm_list:
                                    p_node = p_data['node_id']
                                    if p_node in flow_dict:
                                        for t_node, flow in flow_dict[p_node].items():
                                            if flow > 0:
                                                if t_node == no_match_node:
                                                    reason = "Conflict List" if p_data['id'] not in pnm_ids_with_potential else "Capacity Reached"
                                                    global_flow_results.append({
                                                        'PNM ID': p_data['id'], 'PNM Name': p_data['name'],
                                                        'Bump Team Members': "NO MATCH", 'Match Cost': None, 'Reason': reason,
                                                        'Ranking': None
                                                    })
                                                else:
                                                    match_info = pair_lookup.get((p_node, t_node))
                                                    if match_info:
                                                        global_flow_results.append({
                                                            'PNM ID': p_data['id'], 'PNM Name': p_data['name'],
                                                            'Bump Team Members': match_info['team_members'], 'Match Cost': round(match_info['cost'], 4),
                                                            'Reason': match_info['reasons'],
                                                            'Ranking': match_info['team_ranking']
                                                        })
                                                        assignments_map_flow[match_info['t_idx']].append(match_info)
                            except nx.NetworkXUnfeasible: st.warning(f"Global Flow Unfeasible for Party {party}")

                            global_greedy_results = []
                            assignments_map_greedy = {t['t_idx']: [] for t in team_list}
                            matched_pnm_ids = set()
                            team_counts = {t['t_idx']: 0 for t in team_list}
                            for pair in potential_pairs:
                                if pair['p_id'] not in matched_pnm_ids:
                                    if team_counts[pair['t_idx']] < matches_per_team:
                                        matched_pnm_ids.add(pair['p_id'])
                                        team_counts[pair['t_idx']] += 1
                                        global_greedy_results.append({
                                            'PNM ID': pair['p_id'], 'PNM Name': pair['p_name'],
                                            'Bump Team Members': pair['team_members'], 'Match Cost': round(pair['cost'], 4), 'Reason': pair['reasons'],
                                            'Ranking': pair['team_ranking']
                                        })
                                        assignments_map_greedy[pair['t_idx']].append(pair)
                                        
                            unblocked_pnm_ids = {p['p_id'] for p in potential_pairs}
                        
                            for p_data in pnm_list:
                                if p_data['id'] not in matched_pnm_ids:
                                    was_blocked = p_data['id'] not in unblocked_pnm_ids
                                    reason = "Conflict List" if was_blocked else "Capacity Reached (Greedy)"
                                    global_greedy_results.append({
                                        'PNM ID': p_data['id'], 'PNM Name': p_data['name'],
                                        'Bump Team Members': "NO MATCH", 'Match Cost': None, 'Reason': reason,
                                        'Ranking': None
                                    })

                            def run_internal_rotation(assignment_map, method='flow'):
                                rotation_output = []
                                actual_rounds = 1 if is_bump_order_set == 'y' else num_rounds
                                for t_idx, assigned_pnms in assignment_map.items():
                                    if not assigned_pnms: continue
                                    team_data = next((t for t in team_list if t['t_idx'] == t_idx), None)
                                    if not team_data: continue
                                    raw_rgl = team_data['row_data'].get('RGL', '')
                                    team_rgl_name = "" if pd.isna(raw_rgl) or str(raw_rgl).lower() == 'nan' else str(raw_rgl).strip()
                                    valid_members = []
                                    for m_id, m_name in zip(team_data['member_ids'], team_data['members']):
                                        if m_id: valid_members.append({'id': m_id, 'name': m_name})
                                    history = set()
                                    for round_num in range(1, actual_rounds + 1):
                                        if round_num == 1 and team_rgl_name:
                                            active_members = [m for m in valid_members if m['name'].strip() != team_rgl_name]
                                        else: active_members = valid_members
                                        must_allow_repeats = round_num > len(active_members)
                                        if method == 'flow':
                                            sub_G = nx.DiGraph(); sub_s, sub_t = 's', 't'
                                            req = len(assigned_pnms)
                                            sub_G.add_node(sub_s, demand=-req); sub_G.add_node(sub_t, demand=req)
                                            for p in assigned_pnms: sub_G.add_edge(sub_s, f"p_{p['p_id']}", capacity=1, weight=0)
                                            for m in active_members: sub_G.add_edge(f"m_{m['id']}", sub_t, capacity=1, weight=0)
                                            for p in assigned_pnms:
                                                for m in active_members:
                                                    is_repeat = (str(p['p_id']), str(m['id'])) in history
                                                    if is_repeat and not must_allow_repeats: continue
                                                    m_attrs = member_attr_cache.get(m['id'], set())
                                                    shared = p['p_attrs'].intersection(m_attrs)
                                                    score = sum(trait_weights.get(t, 1.0) for t in shared)
                                                    base_cost = int((1/(1+score))*10000)
                                                    final_cost = base_cost + 50000 if is_repeat else base_cost
                                                    reason = ", ".join(shared) if shared else "Rotation"
                                                    if is_repeat: reason += " (Repeat)"
                                                    sub_G.add_edge(f"p_{p['p_id']}", f"m_{m['id']}", capacity=1, weight=final_cost, reason=reason)
                                            try:
                                                sub_flow = nx.min_cost_flow(sub_G)
                                                for p in assigned_pnms:
                                                    p_node = f"p_{p['p_id']}"
                                                    if p_node in sub_flow:
                                                        for tgt, flow in sub_flow[p_node].items():
                                                            if flow > 0 and tgt != sub_t:
                                                                raw_id = tgt.replace("m_", "")
                                                                m_name = next((m['name'] for m in valid_members if str(m['id']) == raw_id), "Unknown")
                                                                edge_d = sub_G.get_edge_data(p_node, tgt)
                                                                calc_cost = (edge_d.get('weight', 10000) - (50000 if edge_d.get('weight',0) > 40000 else 0)) / 10000.0
                                                                rotation_output.append({
                                                                    'Round': round_num, 'Team ID': t_idx, 'Team Members': team_data['joined_names'],
                                                                    'PNM ID': p['p_id'], 'PNM Name': p['p_name'], 'Matched Member': m_name,
                                                                    'Match Cost': round(calc_cost, 4), 'Reason': f"Common: {edge_d.get('reason')}"
                                                                })
                                                                history.add((str(p['p_id']), str(raw_id)))
                                            except nx.NetworkXUnfeasible:
                                                rotation_output.append({'Round': round_num, 'Team ID': t_idx, 'PNM Name': "FLOW FAIL", 'Reason': "Unfeasible"})
                                        elif method == 'greedy':
                                            candidates = []
                                            for p in assigned_pnms:
                                                for m in active_members:
                                                    is_repeat = (str(p['p_id']), str(m['id'])) in history
                                                    if is_repeat and not must_allow_repeats: continue
                                                    m_attrs = member_attr_cache.get(m['id'], set())
                                                    shared = p['p_attrs'].intersection(m_attrs)
                                                    score = sum(trait_weights.get(t, 1.0) for t in shared)
                                                    final_score = score - 1000 if is_repeat else score
                                                    reason = ", ".join(shared) if shared else "Rotation"
                                                    if is_repeat: reason += " (Repeat)"
                                                    candidates.append((final_score, p, m, reason, is_repeat))
                                            candidates.sort(key=lambda x: x[0], reverse=True)
                                            round_pnm_done, round_mem_done = set(), set()
                                            for sc, p, m, rs, is_rep in candidates:
                                                if p['p_id'] not in round_pnm_done and m['id'] not in round_mem_done:
                                                    real_score = sc + 1000 if is_rep else sc
                                                    rotation_output.append({
                                                        'Round': round_num, 'Team ID': t_idx, 'Team Members': team_data['joined_names'],
                                                        'PNM ID': p['p_id'], 'PNM Name': p['p_name'], 'Matched Member': m['name'],
                                                        'Match Cost': round(1.0/(1.0+real_score), 4), 'Reason': f"Common: {rs}" if real_score > 0 else "Greedy Fill"
                                                    })
                                                    round_pnm_done.add(p['p_id']); round_mem_done.add(m['id'])
                                                    history.add((str(p['p_id']), str(m['id'])))
                                return rotation_output

                            internal_flow_results = run_internal_rotation(assignments_map_flow, method='flow')
                            internal_greedy_results = run_internal_rotation(assignments_map_greedy, method='greedy')

                            def generate_bump_instructions(rotation_data):
                                if not rotation_data: return []
                                df = pd.DataFrame(rotation_data)
                                if df.empty or 'Matched Member' not in df.columns: return []
                                df = df.sort_values(by=['Team ID', 'PNM ID', 'Round'])
                                df['Person_To_Bump'] = df.groupby(['Team ID', 'PNM ID'])['Matched Member'].shift(1)
                                instructions = df[df['Person_To_Bump'].notna()].copy()
                                instructions['At End Of Round'] = instructions['Round'] - 1
                                output = instructions[['Matched Member', 'At End Of Round', 'Person_To_Bump', 'PNM Name']].rename(columns={
                                    'Matched Member': 'Member (You)', 'Person_To_Bump': 'Go Bump This Person', 'PNM Name': 'Who is with PNM'
                                })
                                return output.sort_values(by=['Member (You)', 'At End Of Round']).to_dict('records')

                            bump_instruct_flow = generate_bump_instructions(internal_flow_results)
                            bump_instruct_greedy = generate_bump_instructions(internal_greedy_results)

                            if global_flow_results:
                                output = BytesIO()
                                df_glob_flow = pd.DataFrame(global_flow_results)
                                df_glob_greedy = pd.DataFrame(global_greedy_results)
                                df_rot_flow = pd.DataFrame(internal_flow_results)
                                df_rot_greedy = pd.DataFrame(internal_greedy_results)
                                df_bump_flow = pd.DataFrame(bump_instruct_flow)
                                df_bump_greedy = pd.DataFrame(bump_instruct_greedy)
                                preview_results[party] = df_rot_flow

                                if is_bump_order_set == 'y':
                                    export_df = df_rot_flow[df_rot_flow['Round'] == 1].copy()
                                    export_df = export_df.drop(columns=['Team ID', 'Round', 'Team Members'], errors='ignore')
                                    sheet_suffix = "Round 1 Matches"
                                else:
                                    export_df = df_rot_flow.copy()
                                    export_df = export_df.drop(columns=['Team ID', 'Team Members'], errors='ignore')
                                    sheet_suffix = "Rotation Flow"
                                
                                save_party_to_gsheet(party, export_df, specific_title=f"Party {party} {sheet_suffix}")
                                time.sleep(1.5)

                                
                                flow_strong_count = len(df_glob_flow[df_glob_flow['Ranking'] <= 2])
                                greedy_strong_count = len(df_glob_greedy[df_glob_greedy['Ranking'] <= 2])
                                flow_costs = df_glob_flow['Match Cost'].dropna()
                                greedy_costs = df_glob_greedy['Match Cost'].dropna()
                                summary_data = {
                                    'Metric': ['Total Cost', 'Average Cost', 'Min Cost', 'Max Cost', 'Std Dev', 'Strong Recruiter Teams'],
                                    'Global Network Flow': [
                                        round(flow_costs.sum(), 4), round(flow_costs.mean(), 4) if not flow_costs.empty else 0,
                                        round(flow_costs.min(), 4) if not flow_costs.empty else 0, round(flow_costs.max(), 4) if not flow_costs.empty else 0,
                                        round(flow_costs.std(), 4) if len(flow_costs) > 1 else 0,
                                        flow_strong_count
                                    ],
                                    'Global Greedy': [
                                        round(greedy_costs.sum(), 4), round(greedy_costs.mean(), 4) if not greedy_costs.empty else 0,
                                        round(greedy_costs.min(), 4) if not greedy_costs.empty else 0, round(greedy_costs.max(), 4) if not greedy_costs.empty else 0,
                                        round(greedy_costs.std(), 4) if len(greedy_costs) > 1 else 0,
                                        greedy_strong_count
                                    ]
                                }
                                summary_df = pd.DataFrame(summary_data)
                                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                    summary_df.to_excel(writer, sheet_name="Summary_Comparison", index=False)
                                    auto_adjust_columns(writer, "Summary_Comparison", summary_df)
                                    df_glob_flow.to_excel(writer, sheet_name="Global_Matches_Flow", index=False)
                                    auto_adjust_columns(writer, "Global_Matches_Flow", df_glob_flow)
                                    df_glob_greedy.to_excel(writer, sheet_name="Global_Matches_Greedy", index=False)
                                    auto_adjust_columns(writer, "Global_Matches_Greedy", df_glob_greedy)
                                    if not df_rot_flow.empty:
                                        if is_bump_order_set == "n":
                                            rot_flow_out = df_rot_flow.drop(columns=['Team ID', 'Team Members'], errors='ignore')
                                            rot_flow_out.to_excel(writer, sheet_name="Rotation_Flow", index=False)
                                            auto_adjust_columns(writer, "Rotation_Flow", rot_flow_out)
                                            if not df_bump_flow.empty:
                                                df_bump_flow.to_excel(writer, sheet_name="Bump_Logistics_Flow", index=False)
                                                auto_adjust_columns(writer, "Bump_Logistics_Flow", df_bump_flow)
                                        else:
                                            r1_flow = df_rot_flow[df_rot_flow['Round'] == 1].drop(columns=['Team ID', 'Round', 'Team Members'], errors='ignore')
                                            r1_flow.to_excel(writer, sheet_name="Round_1_Matches_Flow", index=False)
                                            auto_adjust_columns(writer, "Round_1_Matches_Flow", r1_flow)
                                    if not df_rot_greedy.empty:
                                        if is_bump_order_set == "n":
                                            rot_greedy_out = df_rot_greedy.drop(columns=['Team ID', 'Team Members'], errors='ignore')
                                            rot_greedy_out.to_excel(writer, sheet_name="Rotation_Greedy", index=False)
                                            auto_adjust_columns(writer, "Rotation_Greedy", rot_greedy_out)
                                            if not df_bump_greedy.empty:
                                                df_bump_greedy.to_excel(writer, sheet_name="Bump_Logistics_Greedy", index=False)
                                                auto_adjust_columns(writer, "Bump_Logistics_Greedy", df_bump_greedy)
                                        else:
                                            r1_greedy = df_rot_greedy[df_rot_greedy['Round'] == 1].drop(columns=['Team ID', 'Round', 'Team Members'], errors='ignore')
                                            r1_greedy.to_excel(writer, sheet_name="Round_1_Matches_Greedy", index=False)
                                            auto_adjust_columns(writer, "Round_1_Matches_Greedy", r1_greedy)
                                file_content = output.getvalue()
                                file_name_x = f"Party_{party}_Match_Analysis.xlsx"
                                zf.writestr(file_name_x, file_content)
                                individual_party_files.append((f"Party {party}", file_name_x, file_content))

                    st.session_state.match_results = {
                        "zip_data": zip_buffer.getvalue(),
                        "individual_files": individual_party_files,
                        "preview_data": preview_results,
                        "bump_setting": is_bump_order_set
                    }
                    st.success("Matching Complete!")
        
        if st.session_state.match_results:
            st.divider()
            st.subheader("Download Results")
            st.download_button(label="Download All Matches (ZIP)", data=st.session_state.match_results["zip_data"], file_name="recruitment_matches.zip", mime="application/zip")
            st.write("### Individual Party Sheets")
            files = st.session_state.match_results["individual_files"]
            cols_per_row = 4
            for i in range(0, len(files), cols_per_row):
                row_files = files[i : i + cols_per_row]
                cols = st.columns(cols_per_row)
                for idx, (label, fname, data) in enumerate(row_files):
                    with cols[idx]:
                        st.download_button(label=f"Download {label}", data=data, file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_btn_{fname}", use_container_width=True)
    
    # --- TAB 8: LIVE MATCH PREVIEW & EDIT ---
    with tab8:
        st.header("Preview Party Matches and Edit")
        st.caption("This tab scans your Google Sheet for existing match schedules.")

        # 1. Connect to Google Sheets
        client = get_gspread_client()
        
        if client:
            try:
                sh = client.open("OverallMatchingInformation")
                all_worksheets = sh.worksheets()
                all_titles = [ws.title for ws in all_worksheets]

                # 2. Analyze existing sheets to find valid Categories and Parties
                # Map the sheet suffixes to user-friendly "Bump Order" labels
                suffix_map = {
                    "Round 1 Matches": "Yes",
                    "Rotation Flow": "No"
                }
                
                # found_data structure: { "Yes": [1, 2, 3], "No": [1, 2] }
                found_data = {} 

                for title in all_titles:
                    for suffix, bump_label in suffix_map.items():
                        if title.startswith("Party ") and title.endswith(suffix):
                            try:
                                # Extract Party ID: "Party 5 Round 1 Matches" -> "5"
                                parts = title.replace(f" {suffix}", "").replace("Party ", "")
                                party_id = int(parts)
                                
                                if bump_label not in found_data:
                                    found_data[bump_label] = []
                                found_data[bump_label].append(party_id)
                            except ValueError:
                                continue

                # 3. Determine the UI based on what we found
                if not found_data:
                    st.warning("⚠️ No match sheets found in 'OverallMatchingInformation'.")
                    st.info("Please run the matching algorithm or ensure sheets are named 'Party X Round 1 Matches' or 'Party X Rotation Flow'.")
                else:
                    # A. Select Bump Order (instead of Schedule Type)
                    available_bump_options = sorted(found_data.keys(), reverse=True) # Shows 'Yes' then 'No'
                    
                    if len(available_bump_options) > 1:
                        selected_bump = st.radio("Bump Order Set:", available_bump_options, horizontal=True)
                    else:
                        selected_bump = available_bump_options[0]
                        st.info(f"Bump Order Set: **{selected_bump}**")

                    # B. Select Party (filtered by the chosen Bump setting)
                    available_parties = sorted(found_data[selected_bump])
                    
                    if available_parties:
                        st.divider()
                        selected_party = st.selectbox(
                            f"Select Party to Edit:", 
                            available_parties, 
                            format_func=lambda x: f"Party {x}"
                        )
                        
                        # Find the actual suffix to reconstruct the sheet title
                        actual_suffix = [s for s, b in suffix_map.items() if b == selected_bump][0]
                        target_sheet_title = f"Party {selected_party} {actual_suffix}"
                        
                        # 4. Load Data
                        st.markdown(f"### Party {selected_party}")
                        
                        try:
                            worksheet = sh.worksheet(target_sheet_title)
                            raw_data = worksheet.get_all_records()
                            
                            # Convert to DataFrame (all as string)
                            df_to_edit = pd.DataFrame(raw_data).astype(str)
                            
                            # 5. Render Editor & Search Logic
                            if not df_to_edit.empty:
                                
                                # --- NEW: Search Functionality ---
                                search_query = st.text_input("Search within this sheet:", "", key=f"search_{selected_party}")
                                
                                if search_query:
                                    # Filter rows where ANY column contains the search query (case-insensitive)
                                    mask = df_to_edit.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
                                    display_df = df_to_edit[mask]
                                    
                                    # Disable adding/deleting rows while searching to protect index alignment
                                    dynamic_rows_setting = "fixed"
                                    st.caption("*Row additions and deletions are disabled while search is active.*")
                                else:
                                    display_df = df_to_edit.copy()
                                    dynamic_rows_setting = "dynamic"
                                # ---------------------------------

                                edited_df = st.data_editor(
                                    display_df, 
                                    use_container_width=True, 
                                    hide_index=True,
                                    num_rows=dynamic_rows_setting,
                                    key=f"editor_{selected_party}_{selected_bump}"
                                )

                                # 6. Save Button
                                if st.button("Save Changes to Google Drive"):
                                    with st.spinner(f"Saving to '{target_sheet_title}'..."):
                                        
                                        # --- NEW: Merge changes if a search filter was active ---
                                        final_df_to_save = df_to_edit.copy()
                                        if search_query:
                                            # Update the main dataframe with only the edited filtered rows
                                            final_df_to_save.update(edited_df)
                                        else:
                                            final_df_to_save = edited_df
                                        # --------------------------------------------------------

                                        save_success = save_party_to_gsheet(
                                            selected_party, 
                                            final_df_to_save, 
                                            specific_title=target_sheet_title
                                        )
                                        
                                        if save_success:
                                            # Update Session State if it exists
                                            if "match_results" in st.session_state and st.session_state.match_results:
                                                if "preview_data" in st.session_state.match_results:
                                                    st.session_state.match_results["preview_data"][selected_party] = final_df_to_save
                                            
                                            # Regenerate ZIP file
                                            regenerate_zip_from_changes()
                                            
                                            st.success("✅ Saved and Regenerated!")
                                            time.sleep(1)
                                            st.rerun()
                            else:
                                st.warning("This sheet is empty.")

                        except Exception as e:
                            st.error(f"Error loading sheet: {e}")
                    else:
                        st.warning(f"No parties found for Bump Order: {selected_bump}.")

            except Exception as e:
                st.error(f"❌ Connection Error: {e}")
