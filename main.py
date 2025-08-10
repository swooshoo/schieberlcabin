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
import time

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
        border: 2px solid #4b5563;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #374151;
        color: white;
    }
    .pending-column {
        background-color: #fef3c7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem;
    }
    .approved-column {
        background-color: #d1fae5;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem;
    }
    .denied-column {
        background-color: #fee2e2;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem;
    }
    .column-header {
        font-weight: bold;
        font-size: 1.2rem;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()
if 'refresh_data' not in st.session_state:
    st.session_state.refresh_data = 0

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
        
        # Convert Number of Guests to numeric and ensure it's displayed as integer
        if 'Number of Guests' in df.columns:
            df['Number of Guests'] = pd.to_numeric(df['Number of Guests'], errors='coerce')
            # Fill any NaN values with 0 and convert to int
            df['Number of Guests'] = df['Number of Guests'].fillna(0).astype(int)
        
        # FIX FOR PHONE NUMBER FORMATTING
        if 'Phone Number' in df.columns:
            # Convert all phone numbers to strings and handle NaN values
            df['Phone Number'] = df['Phone Number'].astype(str)
            # Replace 'nan' strings with empty strings
            df['Phone Number'] = df['Phone Number'].replace('nan', '')
            # Optional: Format phone numbers consistently
            df['Phone Number'] = df['Phone Number'].apply(format_phone_number)
        
        # Also ensure Email Address is string type (in case of similar issues)
        if 'Email Address' in df.columns:
            df['Email Address'] = df['Email Address'].astype(str)
            df['Email Address'] = df['Email Address'].replace('nan', '')
        
        # Ensure Guest Name is string type
        if 'Guest Name' in df.columns:
            df['Guest Name'] = df['Guest Name'].astype(str)
            df['Guest Name'] = df['Guest Name'].replace('nan', '')
        
        # Ensure Notes is string type
        if 'Notes' in df.columns:
            df['Notes'] = df['Notes'].astype(str)
            df['Notes'] = df['Notes'].replace('nan', '')
        
        # Default Status column to 'Pending' if it doesn't exist or has empty values
        if 'Status' not in df.columns:
            df['Status'] = 'Pending'
        else:
            # Fill any empty or NaN values in Status column with 'Pending'
            df['Status'] = df['Status'].fillna('Pending')
            df['Status'] = df['Status'].replace('', 'Pending')
            df['Status'] = df['Status'].astype(str)  # Ensure it's string type
        
        # Handle any rows with invalid dates
        if 'Check-In' in df.columns and 'Check-Out' in df.columns:
            df = df.dropna(subset=['Check-In', 'Check-Out'])
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {str(e)}")
        st.info("Check your Google Sheets setup and credentials.")
        return pd.DataFrame()

def format_phone_number(phone):
    """
    Format phone number consistently
    """
    if not phone or phone == '' or phone == 'nan':
        return ''
    
    # Remove all non-digit characters
    digits_only = ''.join(filter(str.isdigit, str(phone)))
    
    # Handle different length phone numbers
    if len(digits_only) == 10:
        # Format as (XXX) XXX-XXXX
        return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
    elif len(digits_only) == 11 and digits_only[0] == '1':
        # Handle +1 country code
        return f"({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
    else:
        # Return as-is if it doesn't match expected formats
        return str(phone)

def update_reservation_status(df, row_index, new_status):
    """Update reservation status in Google Sheets"""
    try:
        # Create a connection object
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Create a copy of the dataframe to modify
        updated_df = df.copy()
        
        # Update the status for the specific row
        updated_df.at[row_index, 'Status'] = new_status
        
        # Update the Google Sheet
        conn.update(data=updated_df)
        
        # Force data refresh by incrementing the session state counter
        st.session_state.refresh_data += 1
        
        return True, f"Status updated to {new_status} successfully!"
        
    except Exception as e:
        return False, f"Error updating Google Sheets: {str(e)}"

def create_calendar_view(df, selected_month, selected_year, is_admin=False):
    """Create a calendar view using Plotly with outlined reservation indicators"""
    
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
                calendar_data.append([week_num, day_num, 0, "", "", ""])
            else:
                date = datetime(selected_year, selected_month, day).date()
                
                # Check if there's a reservation for this date in the filtered data
                reservation = None
                reservation_position = ""  # "start", "middle", "end", or "single"
                
                for _, row in month_reservations.iterrows():
                    if row['Check-In'] <= date <= row['Check-Out']:
                        reservation = row
                        
                        # Determine position in reservation
                        if row['Check-In'] == date and row['Check-Out'] == date:
                            reservation_position = "single"
                        elif row['Check-In'] == date:
                            reservation_position = "start"
                        elif row['Check-Out'] == date:
                            reservation_position = "end"
                        else:
                            reservation_position = "middle"
                        break
                
                if reservation is not None:
                    if is_admin:
                        # Admin view: show all reservation statuses with full details
                        if 'Status' in reservation:
                            status_color = 1 if reservation['Status'] == 'Approved' else 0.5 if reservation['Status'] == 'Pending' else 0.2
                        else:
                            status_color = 0.5  # Default to pending if no status
                        # Format number of guests as integer
                        guest_count = int(reservation['Number of Guests']) if pd.notna(reservation['Number of Guests']) else 0
                        hover_text = f"Date: {date}<br>Guest: {reservation['Guest Name']}<br>Status: {reservation.get('Status', 'Pending')}<br>Party: {guest_count} people"
                        
                        # Create day text
                        guest_name_short = reservation['Guest Name'][:6] + "..." if len(reservation['Guest Name']) > 6 else reservation['Guest Name']
                        day_text = f"{day}<br>{guest_name_short}"
                    else:
                        # Public view: only show approved reservations without details
                        if 'Status' in reservation and reservation['Status'] == 'Approved':
                            status_color = 1  # Green for approved
                            hover_text = f"Date: {date}<br>Reserved"  # No guest details
                            day_text = str(day)
                        else:
                            # Don't show pending or denied reservations in public view
                            status_color = 0
                            hover_text = f"Date: {date}<br>Available"
                            day_text = str(day)
                            reservation_position = ""
                else:
                    status_color = 0
                    hover_text = f"Date: {date}<br>Available"
                    day_text = str(day)
                
                calendar_data.append([week_num, day_num, status_color, hover_text, day_text, reservation_position])
    
    # Convert to DataFrame
    cal_df = pd.DataFrame(calendar_data, columns=['week', 'day', 'status', 'hover', 'text', 'position'])
    
    # Create heatmap with no interactivity
    fig = go.Figure(data=go.Heatmap(
        z=cal_df['status'].values.reshape(len(cal), 7),
        x=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        y=[f'Week {i+1}' for i in range(len(cal))],
        colorscale=[[0, '#f3f4f6'], [0.2, '#fee2e2'], [0.5, '#fef3c7'], [1, '#d1fae5']],
        showscale=False,
        hoverinfo='skip'  # Disable hover
    ))
    
    # Add day numbers as annotations
    annotations = []
    for i in range(len(cal)):
        for j in range(7):
            if cal[i][j] != 0:
                day_text = cal_df.iloc[i*7+j]['text']
                position = cal_df.iloc[i*7+j]['position']
                
                # Determine text color based on status
                status = cal_df.iloc[i*7+j]['status']
                if status > 0.8:  # Approved
                    text_color = '#065f46'  # Dark green
                    font_weight = 'bold'
                elif status > 0.3:  # Pending
                    text_color = '#92400e'  # Dark yellow/orange
                    font_weight = 'bold'
                elif status > 0.1:  # Denied
                    text_color = '#991b1b'  # Dark red
                    font_weight = 'bold'
                else:  # Available
                    text_color = '#374151'  # Dark gray
                    font_weight = 'normal'
                
                # Add text annotation
                annotations.append(
                    dict(
                        x=j, y=i,
                        text=day_text,
                        showarrow=False,
                        font=dict(
                            color=text_color, 
                            size=10,
                            weight=font_weight
                        ),
                        xanchor='center',
                        yanchor='middle'
                    )
                )
    
    # Add outline shapes for reservation boundaries
    shapes = []
    for i in range(len(cal)):
        for j in range(7):
            if cal[i][j] != 0:
                position = cal_df.iloc[i*7+j]['position']
                status = cal_df.iloc[i*7+j]['status']
                
                if position and status > 0:  # Only add outlines for reserved days
                    # Determine border style based on position
                    if position == "start":
                        # Thick left border
                        shapes.append(dict(
                            type="line",
                            x0=j-0.5, y0=i-0.5, x1=j-0.5, y1=i+0.5,
                            line=dict(color="black", width=4)
                        ))
                    elif position == "end":
                        # Thick right border
                        shapes.append(dict(
                            type="line",
                            x0=j+0.5, y0=i-0.5, x1=j+0.5, y1=i+0.5,
                            line=dict(color="black", width=4)
                        ))
                    elif position == "single":
                        # Thick left and right borders
                        shapes.append(dict(
                            type="line",
                            x0=j-0.5, y0=i-0.5, x1=j-0.5, y1=i+0.5,
                            line=dict(color="black", width=4)
                        ))
                        shapes.append(dict(
                            type="line",
                            x0=j+0.5, y0=i-0.5, x1=j+0.5, y1=i+0.5,
                            line=dict(color="black", width=4)
                        ))
    
    fig.update_layout(
        annotations=annotations,
        shapes=shapes,
        title=f"{calendar.month_name[selected_month]} {selected_year}",
        height=400,
        yaxis=dict(autorange='reversed'),
        xaxis=dict(side='top', tickangle=0)
    )
    
    # Remove all interactivity
    fig.update_layout(
        dragmode=False,
        #selectdirection='d',
        xaxis=dict(fixedrange=True),
        yaxis=dict(fixedrange=True)
    )
    
    return fig


def admin_panel(df):
    """Enhanced admin panel with three-column layout for reservation management"""
    st.header("Admin Panel")
    
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
        pending_count = len(df[df['Status'] == 'Pending'])
        st.metric("Pending Approval", pending_count)
    
    with col3:
        approved_count = len(df[df['Status'] == 'Approved'])
        st.metric("Approved", approved_count)
    
    with col4:
        denied_count = len(df[df['Status'] == 'Denied'])
        st.metric("Denied", denied_count)
    
    st.divider()
    
    # Admin Calendar Section
    st.subheader("📅 Admin Calendar")
    
    # Calendar controls
    col1, col2 = st.columns(2)
    
    with col1:
        admin_selected_month = st.selectbox("Month", 
                                           options=list(range(1, 13)),
                                           format_func=lambda x: calendar.month_name[x],
                                           index=datetime.now().month - 1,
                                           key="admin_month_select")
    
    with col2:
        admin_selected_year = st.selectbox("Year", 
                                         options=list(range(2025, 2028)),
                                         index=0,
                                         key="admin_year_select")
    
    # Display admin calendar
    admin_calendar_fig = create_calendar_view(df, admin_selected_month, admin_selected_year, is_admin=True)
    st.plotly_chart(admin_calendar_fig, use_container_width=True)
    
    # Enhanced legend for admin calendar
    st.markdown("""
    **Legend:**
    - 🟢 Green: Approved reservation
    - 🟡 Yellow: Pending approval  
    - 🔴 Red: Denied reservation
    - ⚪ White: Available
    
    **Reservation Indicators:**
    - `||Day` : Reservation starts on this day
    - `Day||` : Reservation ends on this day
    - `||Day||` : Single-day reservation
    - `Day` : Middle of multi-day reservation
    """)
    
    st.divider()
    
    # Three-column reservation management
    st.subheader("📋 Reservation Management")
    
    # Filter reservations by status using fresh data
    pending_reservations = df[df['Status'] == 'Pending'].copy()
    approved_reservations = df[df['Status'] == 'Approved'].copy()
    denied_reservations = df[df['Status'] == 'Denied'].copy()
    
    # Create three columns
    col1, col2, col3 = st.columns(3)
    
    # [Rest of the admin_panel function remains the same...]
    # Pending Reservations Column
    with col1:
        st.markdown('<div class="pending-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">⏳ Pending Reservations</div>', unsafe_allow_html=True)
        
        if not pending_reservations.empty:
            for idx, reservation in pending_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Pending')
                
                if action == "approve":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Approved')
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
                
                elif action == "deny":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Denied')
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No pending reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Approved Reservations Column
    with col2:
        st.markdown('<div class="approved-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">✅ Approved Reservations</div>', unsafe_allow_html=True)
        
        if not approved_reservations.empty:
            for idx, reservation in approved_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Approved')
                
                if action == "pending":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Pending')
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No approved reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Denied Reservations Column
    with col3:
        st.markdown('<div class="denied-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">❌ Denied Reservations</div>', unsafe_allow_html=True)
        
        if not denied_reservations.empty:
            for idx, reservation in denied_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Denied')
                
                if action == "approve":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Approved')
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
                
                elif action == "pending":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Pending')
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No denied reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # All reservations table
    st.subheader("📋 All Reservations Table")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Filter by Status", ['All', 'Pending', 'Approved', 'Denied'])
    with col2:
        month_filter = st.selectbox("Filter by Month", 
                                   ['All'] + [calendar.month_name[i] for i in range(1, 13)])
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter != 'All':
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    
    if month_filter != 'All':
        month_num = list(calendar.month_name).index(month_filter)
        filtered_df = filtered_df[filtered_df['Check-In'].apply(lambda x: x.month) == month_num]
    
    # Format the dataframe for display
    display_df = filtered_df.copy()
    if 'Number of Guests' in display_df.columns:
        display_df['Number of Guests'] = display_df['Number of Guests'].astype(int)
    
    # Display table with better formatting
    st.dataframe(
        display_df, 
        use_container_width=True,
        column_config={
            "Number of Guests": st.column_config.NumberColumn(
                "Number of Guests",
                format="%d"
            )
        }
    )


def public_view(df):
    """Public calendar view for guests with enhanced reservation indicators"""
    st.header("Schieberl Cabin Reservations")
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
    calendar_fig = create_calendar_view(df, selected_month, selected_year, is_admin=False)
    st.plotly_chart(calendar_fig, use_container_width=True)
    
    # Enhanced legend for public view
    st.markdown("""
    **Legend:**
    - 🟢 Green: Reserved
    - ⚪ White: Available
    
    **Reservation Indicators:**
    - `||Day` : Reservation starts on this day
    - `Day||` : Reservation ends on this day  
    - `||Day||` : Single-day reservation
    - `Day` : Middle of multi-day reservation
    """)
    
    # Upcoming reservations
    st.subheader("📅 Upcoming Reservations")
    
    # Check if we have the required data for upcoming reservations
    if df.empty or 'Check-In' not in df.columns:
        st.info("No reservation data available.")
        return
    
    # Filter for future approved reservations
    today = datetime.now().date()
    upcoming = df[(df['Check-In'] >= today) & (df['Status'] == 'Approved')].copy()
    upcoming = upcoming.sort_values('Check-In')
    
    if not upcoming.empty:
        for _, reservation in upcoming.iterrows():
            # Format number of guests as integer
            guest_count = int(reservation['Number of Guests']) if pd.notna(reservation['Number of Guests']) else 0
            with st.container():
                st.markdown(f"""
                <div class="reservation-card">
                    <strong>{reservation['Guest Name']}</strong><br>
                    📅 {reservation['Check-In']} to {reservation['Check-Out']}<br>
                    👥 {guest_count} guests<br>
                    <span class="status-approved">Approved</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No upcoming approved reservations.")
    
    # Reservation form link
    st.subheader("📝 Make a Reservation")
    st.markdown("""
    To request a reservation, please fill out the Google Form below:
    
    [**🔗 Cabin Reservation Request Form**](https://forms.google.com/your-form-link)
    
    """)

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

def render_reservation_card(reservation, idx, status_type):
    """Render a reservation card with appropriate styling and actions"""
    guest_count = int(reservation['Number of Guests']) if pd.notna(reservation['Number of Guests']) else 0
    
    with st.container(border=True):
        # Guest information
        st.write(f"**{reservation['Guest Name']}**")
        st.write(f"📧 {reservation['Email Address']}")
        st.write(f"📱 {reservation['Phone Number']}")
        st.write(f"👥 {guest_count} guests")
        
        # Date information
        checkin_day = reservation['Check-In'].strftime('%A')
        checkout_day = reservation['Check-Out'].strftime('%A')
        st.write(f"📅 **Check-in:** {reservation['Check-In']}, {checkin_day}")
        st.write(f"📅 **Check-out:** {reservation['Check-Out']}, {checkout_day}")
        duration = (reservation['Check-Out'] - reservation['Check-In']).days
        st.write(f"🏠 **Duration:** {duration} nights")
        
        # Notes
        if reservation['Notes'] and str(reservation['Notes']).strip():
            st.write(f"📝 **Notes:** {reservation['Notes']}")
        
        # Admin notes for denied reservations
        if status_type == 'Denied' and 'Admin Notes' in reservation and reservation['Admin Notes']:
            st.write(f"❌ **Admin Notes:** {reservation['Admin Notes']}")
        
        # Action buttons based on status
        if status_type == 'Pending':
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"approve_{idx}", use_container_width=True):
                    return "approve"
            with col2:
                if st.button("❌ Deny", key=f"deny_{idx}", use_container_width=True):
                    return "deny"
        
        elif status_type == 'Approved':
            if st.button("🔄 Move to Pending", key=f"pending_{idx}", use_container_width=True):
                return "pending"
        
        elif status_type == 'Denied':
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"approve_denied_{idx}", use_container_width=True):
                    return "approve"
            with col2:
                if st.button("🔄 Move to Pending", key=f"pending_denied_{idx}", use_container_width=True):
                    return "pending"
        
    return None

def admin_panel(df):
    """Enhanced admin panel with three-column layout for reservation management"""
    st.header("Admin Panel")
    
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
        pending_count = len(df[df['Status'] == 'Pending'])
        st.metric("Pending Approval", pending_count)
    
    with col3:
        approved_count = len(df[df['Status'] == 'Approved'])
        st.metric("Approved", approved_count)
    
    with col4:
        denied_count = len(df[df['Status'] == 'Denied'])
        st.metric("Denied", denied_count)
    
    st.divider()
    
    # Admin Calendar Section
    st.subheader("📅 Admin Calendar")
    
    # Calendar controls
    col1, col2 = st.columns(2)
    
    with col1:
        admin_selected_month = st.selectbox("Month", 
                                           options=list(range(1, 13)),
                                           format_func=lambda x: calendar.month_name[x],
                                           index=datetime.now().month - 1,
                                           key="admin_month_select")
    
    with col2:
        admin_selected_year = st.selectbox("Year", 
                                         options=list(range(2025, 2028)),
                                         index=0,
                                         key="admin_year_select")
    
    # Display admin calendar
    admin_calendar_fig = create_calendar_view(df, admin_selected_month, admin_selected_year, is_admin=True)
    st.plotly_chart(admin_calendar_fig, use_container_width=True)
    
    # Legend for admin calendar
    st.markdown("""
    **Legend:**
    - 🟢 Green: Approved reservation
    - 🟡 Yellow: Pending approval
    - 🔴 Red: Denied reservation
    - ⚪ White: Available
    """)
    
    st.divider()
    
    # Three-column reservation management
    st.subheader("📋 Reservation Management")
    
    # Filter reservations by status using fresh data
    pending_reservations = df[df['Status'] == 'Pending'].copy()
    approved_reservations = df[df['Status'] == 'Approved'].copy()
    denied_reservations = df[df['Status'] == 'Denied'].copy()
    
    # Create three columns
    col1, col2, col3 = st.columns(3)
    
    # Pending Reservations Column
    with col1:
        st.markdown('<div class="pending-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">⏳ Pending Reservations</div>', unsafe_allow_html=True)
        
        if not pending_reservations.empty:
            for idx, reservation in pending_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Pending')
                
                if action == "approve":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Approved')
                        if success:
                            st.success(message)
                            time.sleep(0.5)  # Brief pause to ensure update completes
                            st.rerun()
                        else:
                            st.error(message)
                
                elif action == "deny":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Denied')
                        if success:
                            st.success(message)
                            time.sleep(0.5)  # Brief pause to ensure update completes
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No pending reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Approved Reservations Column
    with col2:
        st.markdown('<div class="approved-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">✅ Approved Reservations</div>', unsafe_allow_html=True)
        
        if not approved_reservations.empty:
            for idx, reservation in approved_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Approved')
                
                if action == "pending":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Pending')
                        if success:
                            st.success(message)
                            time.sleep(0.5)  # Brief pause to ensure update completes
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No approved reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Denied Reservations Column
    with col3:
        st.markdown('<div class="denied-column">', unsafe_allow_html=True)
        st.markdown('<div class="column-header">❌ Denied Reservations</div>', unsafe_allow_html=True)
        
        if not denied_reservations.empty:
            for idx, reservation in denied_reservations.iterrows():
                action = render_reservation_card(reservation, idx, 'Denied')
                
                if action == "approve":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Approved')
                        if success:
                            st.success(message)
                            time.sleep(0.5)  # Brief pause to ensure update completes
                            st.rerun()
                        else:
                            st.error(message)
                
                elif action == "pending":
                    with st.spinner("Updating status..."):
                        success, message = update_reservation_status(df, idx, 'Pending')
                        if success:
                            st.success(message)
                            time.sleep(0.5)  # Brief pause to ensure update completes
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No denied reservations")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # All reservations table (existing functionality)
    st.subheader("📋 All Reservations Table")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Filter by Status", ['All', 'Pending', 'Approved', 'Denied'])
    with col2:
        month_filter = st.selectbox("Filter by Month", 
                                   ['All'] + [calendar.month_name[i] for i in range(1, 13)])
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter != 'All':
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    
    if month_filter != 'All':
        month_num = list(calendar.month_name).index(month_filter)
        filtered_df = filtered_df[filtered_df['Check-In'].apply(lambda x: x.month) == month_num]
    
    # Format the dataframe for display
    display_df = filtered_df.copy()
    if 'Number of Guests' in display_df.columns:
        display_df['Number of Guests'] = display_df['Number of Guests'].astype(int)
    
    # Display table with better formatting
    st.dataframe(
        display_df, 
        use_container_width=True,
        column_config={
            "Number of Guests": st.column_config.NumberColumn(
                "Number of Guests",
                format="%d"
            )
        }
    )

def public_view(df):
    """Public calendar view for guests with enhanced reservation indicators"""
    st.header("Schieberl Cabin Reservations")
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
    calendar_fig = create_calendar_view(df, selected_month, selected_year, is_admin=False)
    st.plotly_chart(calendar_fig, use_container_width=True)
    
    # Enhanced legend for public view
    st.markdown("""
    **Legend:**
    - 🟢 Green: Reserved
    - ⚪ White: Available
    
    **Reservation Indicators:**
    - `||Day` : Reservation starts on this day
    - `Day||` : Reservation ends on this day  
    - `||Day||` : Single-day reservation
    - `Day` : Middle of multi-day reservation
    """)
    
    # Upcoming reservations
    st.subheader("📅 Upcoming Reservations")
    
    # Check if we have the required data for upcoming reservations
    if df.empty or 'Check-In' not in df.columns:
        st.info("No reservation data available.")
        return
    
    # Filter for future approved reservations
    today = datetime.now().date()
    upcoming = df[(df['Check-In'] >= today) & (df['Status'] == 'Approved')].copy()
    upcoming = upcoming.sort_values('Check-In')
    
    if not upcoming.empty:
        for _, reservation in upcoming.iterrows():
            # Format number of guests as integer
            guest_count = int(reservation['Number of Guests']) if pd.notna(reservation['Number of Guests']) else 0
            with st.container():
                st.markdown(f"""
                <div class="reservation-card">
                    <strong>{reservation['Guest Name']}</strong><br>
                    📅 {reservation['Check-In']} to {reservation['Check-Out']}<br>
                    👥 {guest_count} guests<br>
                    <span class="status-approved">Approved</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No upcoming approved reservations.")
    
    # Reservation form link
    st.subheader("📝 Make a Reservation")
    st.markdown("""
    To request a reservation, please fill out the Google Form below:
    
    [**🔗 Cabin Reservation Request Form**](https://forms.google.com/your-form-link)
    
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