import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import calendar
import datetime
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json

# Page configuration
st.set_page_config(
    page_title="Schieberl Cabin Reservations",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }
    .status-approved {
        background-color: #d1fae5;
        color: #065f46;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .status-pending {
        background-color: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .status-rejected {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .reservation-card {
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #f9fafb;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

def load_google_sheets_data():
    """Load data from Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        credentials_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
        
        gc = gspread.authorize(credentials)
        sheet_id = st.secrets["google_sheet_id"]
        sheet = gc.open_by_key(sheet_id).sheet1
        
        # Get all records
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        
        # Convert date columns
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date']).dt.date
        df['Check-out Date'] = pd.to_datetime(df['Check-out Date']).dt.date
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def connect_to_google_sheets():
    """
    Setup Google Sheets connection
    You'll need to add your credentials here
    """
    # Instructions for setup:
    """
    1. Go to Google Cloud Console
    2. Create a new project or select existing
    3. Enable Google Sheets API
    4. Create service account credentials
    5. Download JSON key file
    6. Share your Google Sheet with the service account email
    7. Add the JSON content to Streamlit secrets
    """
    
    # Example connection code (uncomment and modify):
    """
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    # Load credentials from Streamlit secrets
    credentials_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
    
    gc = gspread.authorize(credentials)
    sheet = gc.open("Tahoe Cabin Reservations").sheet1
    
    return sheet
    """
    pass

def create_calendar_view(df, selected_month, selected_year):
    """Create an interactive calendar view using Plotly"""
    
    # Create calendar data
    cal = calendar.monthcalendar(selected_year, selected_month)
    
    # Prepare data for heatmap
    days_in_month = calendar.monthrange(selected_year, selected_month)[1]
    calendar_data = []
    
    for week_num, week in enumerate(cal):
        for day_num, day in enumerate(week):
            if day == 0:
                calendar_data.append([week_num, day_num, 0, "", ""])
            else:
                date = datetime(selected_year, selected_month, day).date()
                
                # Check if there's a reservation for this date
                reservation = None
                for _, row in df.iterrows():
                    if row['Check-in Date'] <= date <= row['Check-out Date']:
                        reservation = row
                        break
                
                if reservation is not None:
                    status_color = 1 if reservation['Status'] == 'Approved' else 0.5
                    hover_text = f"Date: {date}<br>Guest: {reservation['Guest Name']}<br>Status: {reservation['Status']}<br>Party: {reservation['Party Size']} people"
                    day_text = f"{day}<br>{reservation['Guest Name'][:8]}..."
                else:
                    status_color = 0
                    hover_text = f"Date: {date}<br>Available"
                    day_text = str(day)
                
                calendar_data.append([week_num, day_num, status_color, hover_text, day_text])
    
    # Convert to DataFrame
    cal_df = pd.DataFrame(calendar_data, columns=['week', 'day', 'status', 'hover', 'text'])
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=cal_df['status'].values.reshape(len(cal), 7),
        x=['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        y=[f'Week {i+1}' for i in range(len(cal))],
        colorscale=[[0, '#f3f4f6'], [0.5, '#fef3c7'], [1, '#d1fae5']],
        showscale=False,
        hovertemplate='%{text}<extra></extra>',
        text=[[cal_df.iloc[i*7+j]['hover'] for j in range(7)] for i in range(len(cal))]
    ))
    
    # Add day numbers as annotations
    annotations = []
    for i in range(len(cal)):
        for j in range(7):
            if cal[i][j] != 0:
                annotations.append(
                    dict(
                        x=j, y=i,
                        text=str(cal[i][j]),
                        showarrow=False,
                        font=dict(color='black', size=12)
                    )
                )
    
    fig.update_layout(
        annotations=annotations,
        title=f"{calendar.month_name[selected_month]} {selected_year}",
        height=400,
        yaxis=dict(autorange='reversed')
    )
    
    return fig

def update_reservation_status(reservation_id, new_status):
    """Update reservation status in Google Sheets"""
    # This would update the Google Sheet
    # For demo, we'll just show a success message
    st.success(f"Reservation status updated to: {new_status}")

def admin_panel(df):
    """Admin panel for managing reservations"""
    st.header("🔧 Admin Panel")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_reservations = len(df)
        st.metric("Total Reservations", total_reservations)
    
    with col2:
        pending_count = len(df[df['Status'] == 'Pending'])
        st.metric("Pending Approval", pending_count)
    
    with col3:
        approved_count = len(df[df['Status'] == 'Approved'])
        st.metric("Approved", approved_count)
    
    with col4:
        occupancy_rate = f"{(approved_count / max(total_reservations, 1) * 100):.1f}%"
        st.metric("Approval Rate", occupancy_rate)
    
    st.divider()
    
    # Pending reservations for review
    pending_reservations = df[df['Status'] == 'Pending'].copy()
    
    if not pending_reservations.empty:
        st.subheader("⏳ Pending Reservations")
        
        for idx, reservation in pending_reservations.iterrows():
            with st.container():
                st.markdown('<div class="reservation-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**{reservation['Guest Name']}**")
                    st.write(f"📧 {reservation['Email']}")
                    st.write(f"📱 {reservation['Phone']}")
                    st.write(f"👥 {reservation['Party Size']} guests")
                
                with col2:
                    st.write(f"📅 **Check-in:** {reservation['Check-in Date']}")
                    st.write(f"📅 **Check-out:** {reservation['Check-out Date']}")
                    duration = (reservation['Check-out Date'] - reservation['Check-in Date']).days
                    st.write(f"🏠 **Duration:** {duration} nights")
                    if reservation['Special Requests'] != 'None':
                        st.write(f"📝 **Special Requests:** {reservation['Special Requests']}")
                
                with col3:
                    if st.button("✅ Approve", key=f"approve_{idx}"):
                        update_reservation_status(idx, "Approved")
                        st.rerun()
                    
                    if st.button("❌ Reject", key=f"reject_{idx}"):
                        update_reservation_status(idx, "Rejected")
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.divider()
    else:
        st.info("No pending reservations to review.")
    
    # All reservations table
    st.subheader("📋 All Reservations")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Filter by Status", ['All', 'Pending', 'Approved', 'Rejected'])
    with col2:
        month_filter = st.selectbox("Filter by Month", 
                                   ['All'] + [calendar.month_name[i] for i in range(1, 13)])
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter != 'All':
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    
    if month_filter != 'All':
        month_num = list(calendar.month_name).index(month_filter)
        filtered_df = filtered_df[filtered_df['Check-in Date'].apply(lambda x: x.month) == month_num]
    
    # Display table
    st.dataframe(filtered_df, use_container_width=True)

def public_view(df):
    """Public calendar view for guests"""
    st.markdown('<p class="main-header">🏔️ Tahoe Cabin Reservations</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">View availability and upcoming reservations</p>', unsafe_allow_html=True)
    
    # Calendar controls
    col1, col2 = st.columns(2)
    
    with col1:
        selected_month = st.selectbox("Month", 
                                     options=list(range(1, 13)),
                                     format_func=lambda x: calendar.month_name[x],
                                     index=datetime.now().month - 1)
    
    with col2:
        selected_year = st.selectbox("Year", 
                                    options=list(range(2025, 2028)),
                                    index=0)
    
    # Display calendar
    calendar_fig = create_calendar_view(df, selected_month, selected_year)
    st.plotly_chart(calendar_fig, use_container_width=True)
    
    # Legend
    st.markdown("""
    **Legend:**
    - 🟢 Green: Approved reservation
    - 🟡 Yellow: Pending approval
    - ⚪ White: Available
    """)
    
    # Upcoming reservations
    st.subheader("📅 Upcoming Reservations")
    
    # Filter for future approved reservations
    today = datetime.now().date()
    upcoming = df[(df['Check-in Date'] >= today) & (df['Status'] == 'Approved')].copy()
    upcoming = upcoming.sort_values('Check-in Date')
    
    if not upcoming.empty:
        for _, reservation in upcoming.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="reservation-card">
                    <strong>{reservation['Guest Name']}</strong><br>
                    📅 {reservation['Check-in Date']} to {reservation['Check-out Date']}<br>
                    👥 {reservation['Party Size']} guests<br>
                    <span class="status-approved">Approved</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No upcoming approved reservations.")
    
    # Reservation form link
    st.subheader("📝 Make a Reservation")
    st.markdown("""
    To request a reservation, please fill out our Google Form:
    
    [**🔗 Cabin Reservation Request Form**](https://docs.google.com/forms/d/1ZjP-MmFb3-3tVyg9O5t9d1129zw6s7WLFGoEFS80YhY/edit)
    
    *Note: All reservations are subject to approval. You will receive confirmation within 24-48 hours.*
    """)

def main():
    """Main application"""
    
    # Sidebar
    with st.sidebar:
        st.title("🏔️ Tahoe Cabin")
        
        # Admin toggle
        admin_password = st.text_input("Admin Password", type="password")
        if admin_password == "admin123":  # Change this to a secure password
            st.session_state.admin_mode = True
            st.success("Admin access granted")
        elif admin_password:
            st.error("Invalid password")
            st.session_state.admin_mode = False
        
        st.divider()
        
        # View selector
        if st.session_state.admin_mode:
            view_mode = st.radio("View Mode", ["Public Calendar", "Admin Panel"])
        else:
            view_mode = "Public Calendar"
        
        st.divider()
        
        # Instructions
        st.markdown("""
        ### 📋 How it works:
        1. **Guests** fill out the Google Form
        2. **Admin** reviews and approves requests
        3. **Calendar** shows approved reservations
        4. **Everyone** can view availability
        """)
        
        # Google Sheets setup info
        if st.session_state.admin_mode:
            with st.expander("🔧 Setup Instructions"):
                st.markdown("""
                **Google Sheets Integration:**
                1. Create a Google Form for reservations
                2. Link form responses to Google Sheets
                3. Set up Google Sheets API credentials
                4. Update the `connect_to_google_sheets()` function
                5. Add credentials to Streamlit secrets
                
                **Required columns in Google Sheets:**
                - Timestamp
                - Guest Name
                - Email
                - Phone
                - Check-in Date
                - Check-out Date
                - Party Size
                - Special Requests
                - Status (add manually for admin approval)
                """)
    
    # Load data
    df = load_google_sheets_data()
    
    # Main content
    if st.session_state.admin_mode and view_mode == "Admin Panel":
        admin_panel(df)
    else:
        public_view(df)
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #6b7280; font-size: 0.875rem;'>
        Built with ❤️ using Streamlit • Last updated: August 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()