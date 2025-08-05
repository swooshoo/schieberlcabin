import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
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
    .status-denied {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .reservation-card {
        border: 1px solid #4b5563;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #374151;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

def load_google_sheets_data():
    """
    Load data from Google Sheets using streamlit-gsheets connection
    """
    try:
        # Create a connection object
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Read the Google Sheet data with a caching mechanism
        df = conn.read(ttl="10s")
        
        # Handle empty DataFrame
        if df.empty:
            st.warning("No data found in Google Sheets. Please add some reservation data.")
            return pd.DataFrame()
        
        # Convert date columns - handle different possible date formats
        if 'Check-In' in df.columns:
            df['Check-In'] = pd.to_datetime(df['Check-In'], errors='coerce').dt.date
        if 'Check-Out' in df.columns:
            df['Check-Out'] = pd.to_datetime(df['Check-Out'], errors='coerce').dt.date
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        
        # Convert Number of Guests to numeric (since it comes as string from form)
        if 'Number of Guests' in df.columns:
            df['Number of Guests'] = pd.to_numeric(df['Number of Guests'], errors='coerce')
        
        # Handle any rows with invalid dates
        if 'Check-In' in df.columns and 'Check-Out' in df.columns:
            df = df.dropna(subset=['Check-In', 'Check-Out'])
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {str(e)}")
        st.info("Check your Google Sheets setup and credentials.")
        return pd.DataFrame()

def connect_to_google_sheets():
    """
    Setup Google Sheets connection
    You'll need to add your credentials here
    """
    pass

def create_calendar_view(df, selected_month, selected_year):
    """Create an interactive calendar view using Plotly"""
    
    # Check if DataFrame is empty or missing required columns
    if df.empty:
        return create_empty_calendar(selected_month, selected_year)
    
    required_columns = ['Check-In', 'Check-Out', 'Guest Name', 'Status', 'Number of Guests']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {missing_columns}")
        st.write("Available columns:", list(df.columns))
        return create_empty_calendar(selected_month, selected_year)
    
    # Filter reservations to only those that overlap with the selected month
    month_start = datetime(selected_year, selected_month, 1).date()
    if selected_month == 12:
        month_end = datetime(selected_year + 1, 1, 1).date() - timedelta(days=1)
    else:
        month_end = datetime(selected_year, selected_month + 1, 1).date() - timedelta(days=1)
    
    # Filter reservations that overlap with this month
    month_reservations = df[
        (df['Check-In'] <= month_end) & (df['Check-Out'] >= month_start)
    ].copy()
    
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
                
                # Check if there's a reservation for this date in the filtered data
                reservation = None
                for _, row in month_reservations.iterrows():
                    if row['Check-In'] <= date <= row['Check-Out']:
                        reservation = row
                        break
                
                if reservation is not None:
                    if 'Status' in reservation:
                        status_color = 1 if reservation['Status'] == 'Approved' else 0.5 if reservation['Status'] == 'Pending' else 0.2
                    else:
                        status_color = 0.5  # Default to pending if no status
                    hover_text = f"Date: {date}<br>Guest: {reservation['Guest Name']}<br>Status: {reservation.get('Status', 'Pending')}<br>Party: {reservation['Number of Guests']} people"
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
        yaxis=dict(autorange='reversed'),
        xaxis=dict(side='top', tickangle=0)
    )
    
    return fig

def create_empty_calendar(selected_month, selected_year):
    """Create an empty calendar when no data is available"""
    # Create calendar data
    cal = calendar.monthcalendar(selected_year, selected_month)
    
    # Create empty calendar
    calendar_data = []
    for week_num, week in enumerate(cal):
        for day_num, day in enumerate(week):
            if day == 0:
                calendar_data.append([week_num, day_num, 0, "", ""])
            else:
                date = datetime(selected_year, selected_month, day).date()
                hover_text = f"Date: {date}<br>Available"
                calendar_data.append([week_num, day_num, 0, hover_text, str(day)])
    
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
        title=f"{calendar.month_name[selected_month]} {selected_year} - No Data Available",
        height=400,
        yaxis=dict(autorange='reversed'),
        xaxis=dict(side='top', tickangle=0)
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
    
    # Check if DataFrame is empty
    if df.empty:
        st.warning("No reservation data available. Please check your Google Sheets connection.")
        return
    
    # Check for required columns
    required_columns = ['Status', 'Guest Name', 'Email Address', 'Phone Number', 'Check-In', 'Check-Out', 'Number of Guests', 'Notes']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {missing_columns}")
        st.write("Available columns:", list(df.columns))
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_reservations = len(df)
        st.metric("Total Reservations", total_reservations)
    
    with col2:
        if 'Status' in df.columns:
            pending_count = len(df[df['Status'] == 'Pending'])
        else:
            pending_count = len(df)  # All are pending if no Status column
        st.metric("Pending Approval", pending_count)
    
    with col3:
        if 'Status' in df.columns:
            approved_count = len(df[df['Status'] == 'Approved'])
        else:
            approved_count = 0
        st.metric("Approved", approved_count)
    
    with col4:
        if 'Status' in df.columns:
            denied_count = len(df[df['Status'] == 'Denied'])
        else:
            denied_count = 0
        st.metric("Denied", denied_count)
    
    st.divider()
    
    # Pending reservations for review
    if 'Status' in df.columns:
        pending_reservations = df[df['Status'] == 'Pending'].copy()
    else:
        # If no Status column, treat all as pending
        pending_reservations = df.copy()
        pending_reservations['Status'] = 'Pending'
    
    if not pending_reservations.empty:
        st.subheader("⏳ Pending Reservations")
        
        for idx, reservation in pending_reservations.iterrows():
            with st.container():
                st.markdown('<div class="reservation-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**{reservation['Guest Name']}**")
                    st.write(f"📧 {reservation['Email Address']}")
                    st.write(f"📱 {reservation['Phone Number']}")
                    st.write(f"👥 {reservation['Number of Guests']} guests")
                
                with col2:
                    checkin_day = reservation['Check-In'].strftime('%A')
                    checkout_day = reservation['Check-Out'].strftime('%A')
                    st.write(f"📅 **Check-in:** {reservation['Check-In']}, {checkin_day}")
                    st.write(f"📅 **Check-out:** {reservation['Check-Out']}, {checkout_day}")
                    duration = (reservation['Check-Out'] - reservation['Check-In']).days
                    st.write(f"🏠 **Duration:** {duration} nights")
                    if reservation['Notes'] and str(reservation['Notes']).strip():
                        st.write(f"📝 **Notes:** {reservation['Notes']}")
                
                with col3:
                    if st.button("✅ Approve", key=f"approve_{idx}"):
                        update_reservation_status(idx, "Approved")
                        st.rerun()
                    
                    if st.button("❌ Deny", key=f"deny_{idx}"):
                        update_reservation_status(idx, "Denied")
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
        status_filter = st.selectbox("Filter by Status", ['All', 'Pending', 'Approved', 'Denied'])
    with col2:
        month_filter = st.selectbox("Filter by Month", 
                                   ['All'] + [calendar.month_name[i] for i in range(1, 13)])
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter != 'All' and 'Status' in df.columns:
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    
    if month_filter != 'All':
        month_num = list(calendar.month_name).index(month_filter)
        filtered_df = filtered_df[filtered_df['Check-In'].apply(lambda x: x.month) == month_num]
    
    # Display table
    st.dataframe(filtered_df, use_container_width=True)

def public_view(df):
    """Public calendar view for guests"""
    st.markdown('<p class="main-header">🏔️ Schieberl Cabin Reservations</p>', unsafe_allow_html=True)
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
    
    # Check if we have the required data for upcoming reservations
    if df.empty or 'Check-In' not in df.columns:
        st.info("No reservation data available.")
        return
    
    # Filter for future approved reservations
    today = datetime.now().date()
    if 'Status' in df.columns:
        upcoming = df[(df['Check-In'] >= today) & (df['Status'] == 'Approved')].copy()
    else:
        # If no Status column, show all future reservations
        upcoming = df[df['Check-In'] >= today].copy()
    upcoming = upcoming.sort_values('Check-In')
    
    if not upcoming.empty:
        for _, reservation in upcoming.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="reservation-card">
                    <strong>{reservation['Guest Name']}</strong><br>
                    📅 {reservation['Check-In']} to {reservation['Check-Out']}<br>
                    👥 {reservation['Number of Guests']} guests<br>
                    <span class="status-approved">{'Approved' if 'Status' in reservation and reservation['Status'] == 'Approved' else 'Pending Review'}</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No upcoming approved reservations.")
    
    # Reservation form link
    st.subheader("📝 Make a Reservation")
    st.markdown("""
    To request a reservation, please fill out our Google Form:
    
    [**🔗 Cabin Reservation Request Form**](https://forms.google.com/your-form-link)
    
    *Note: All reservations are subject to approval. You will receive confirmation within 24-48 hours.*
    """)

def main():
    """Main application"""
    
    # Sidebar
    with st.sidebar:
        st.title("🏔️ Schieberl Cabin")
        
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
    
    # Load data
    df = load_google_sheets_data()
    
    # Debug: Show column names (remove this in production)
    # if st.session_state.admin_mode:
    #     with st.expander("Debug Info"):
    #         st.write("DataFrame columns:", list(df.columns))
    #         st.write("DataFrame shape:", df.shape)
    #         if not df.empty:
    #             st.write("Sample data:")
    #             st.dataframe(df.head())
    
    # Main content
    if st.session_state.admin_mode and view_mode == "Admin Panel":
        admin_panel(df)
    else:
        public_view(df)
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #6b7280; font-size: 0.875rem;'>
        Built by Eliot using Streamlit • Last updated: August 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()