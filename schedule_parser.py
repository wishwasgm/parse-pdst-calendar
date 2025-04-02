import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import PyPDF2
import io
import csv

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def parse_time(time_str):
    """Convert time string to datetime.time object with PM handling"""
    try:
        # Split hours and minutes
        time_parts = time_str.strip().split(':')
        if len(time_parts) == 2:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            # If hour is between 1 and 11, and we're parsing a time that should be PM,
            # add 12 hours to convert to 24-hour format
            if 1 <= hour <= 11:
                # Assume times between 1:00-5:59 are PM
                hour += 12
            
            return datetime.strptime(f"{hour:02d}:{minute:02d}", '%H:%M').time()
    except ValueError:
        return None

    """Convert time string to datetime.time object without AM/PM conversion"""
    try:
        # First try parsing just hours and minutes
        time_parts = time_str.strip().split(':')
        if len(time_parts) == 2:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            return datetime.strptime(f"{hour:02d}:{minute:02d}", '%H:%M').time()
    except ValueError:
        return None


def parse_location(text):
    """Extract location from text"""
    locations = {
        'Hazen': 'Hazen Pool',
        'MW': 'Mary Wayte Pool',
        'SU': 'Seattle University Pool',
        'KCAC': 'King County Aquatic Center',
        'BAC': 'Bellevue Aquatic Center',
        'Tukwila': 'Tukwila Pool',
        'Evergreen': 'Evergreen Pool'
    }
    
    for key, value in locations.items():
        if key in text:
            return value
    return None

def parse_date(date_str):
    """Parse date string into datetime object using current year"""
    current_year = datetime.now().year
    
    try:
        if 'Mar-' in date_str:
            date_str = date_str.replace('Mar-', 'March-')
            month = 3
        elif 'April-' in date_str:
            month = 4
        elif 'May-' in date_str:
            month = 5
        else:
            return None
            
        day = int(date_str.split('-')[1])
        
        # Create the date
        date = datetime(current_year, month, day)
        
        # If the date is more than 6 months in the past, assume it's for next year
        if (datetime.now() - date).days > 180:
            date = datetime(current_year + 1, month, day)
            
        return date
    except:
        return None

def format_datetime(dt):
    """Format datetime for Google Calendar CSV"""
    return dt.strftime('%m/%d/%Y %I:%M %p')

def create_google_calendar_csv(events):
    """Create CSV file in Google Calendar format"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Subject',
        'Start Date',
        'Start Time',
        'End Date',
        'End Time',
        'All Day Event',
        'Description',
        'Location',
        'Private'
    ])
    
    # Write events
    for event in events:
        writer.writerow([
            event['summary'],
            event['start'].strftime('%m/%d/%Y'),
            event['start'].strftime('%I:%M %p'),
            event['end'].strftime('%m/%d/%Y'),
            event['end'].strftime('%I:%M %p'),
            'False',
            event.get('description', ''),
            event.get('location', ''),
            'False'
        ])
    
    return output.getvalue()

def filter_events(events, filter_text):
    """
    Filter events based on multiple search terms (comma-separated)
    Returns events that match ANY of the filter terms
    """
    if not filter_text:
        return events
        
    # Split filter text by commas and clean up terms
    filter_terms = [term.strip().lower() for term in filter_text.split(',') if term.strip()]
    
    # Return events that match any of the filter terms
    filtered_events = []
    for event in events:
        if any(term in event['summary'].lower() for term in filter_terms):
            filtered_events.append(event)
    
    return filtered_events

def main():
    st.title("Swimming Schedule Parser")
    st.write("Convert swimming schedule PDF to Google Calendar format")
    
    # Display current year being used
    current_year = datetime.now().year
    st.info(f"Using current year: {current_year} for all dates")
    
    uploaded_file = st.file_uploader("Upload schedule PDF file", type=['pdf'])
    
    if uploaded_file:
        try:
            # Extract text from PDF
            pdf_text = extract_text_from_pdf(uploaded_file)
            
            # Store events
            events = []
            
            # Parse the schedule
            lines = pdf_text.split('\n')
            current_date = None
            
            # Process each line
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Check for date lines
                if any(month in line for month in ['March-', 'Mar-', 'April-', 'May-']):
                    date_matches = re.findall(r'((?:March|Mar|April|May)-\d+)', line)
                    if date_matches:
                        current_date = parse_date(date_matches[0])
                    continue
                
                # Parse training sessions
                if '@' in line:
                    # Extract time and location
                    time_loc = line.split('@')
                    if len(time_loc) != 2:
                        continue
                        
                    time_part = time_loc[0]
                    location = parse_location(time_loc[1])
                    
                    # Extract times
                    times = re.findall(r'(\d+:\d+)-(\d+:\d+)(?:am|pm)?', time_part)
                    if not times:
                        continue
                        
                    start_time, end_time = times[0]
                    
                    # Create event
                    group = line.split()[0] if line.split() else "Training"
                    summary = f"{group} Swimming Training"
                    
                    # Add event
                    if current_date:
                        try:
                            start_datetime = datetime.combine(current_date, parse_time(start_time))
                            end_datetime = datetime.combine(current_date, parse_time(end_time))
                            
                            event = {
                                'summary': summary,
                                'start': start_datetime,
                                'end': end_datetime,
                                'location': location,
                                'original_text': line.strip()
                            }
                            events.append(event)
                        except Exception as e:
                            st.error(f"Error creating event: {e}")
            
            # Display filtering options
            st.write("### Filter Events")
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                filter_text = st.text_input(
                    "Filter by group names (comma-separated, e.g., 'Senior, Adv1, HSG2')",
                    help="Enter multiple terms separated by commas. Events matching ANY term will be shown."
                )
            with col2:
                show_original = st.checkbox("Show original text")
            with col3:
                sort_order = st.selectbox(
                    "Sort by",
                    options=["Date & Time", "Group Name"],
                    index=0
                )
            
            # Filter events
            filtered_events = filter_events(events, filter_text)
            
            # Sort events based on user preference
            if sort_order == "Group Name":
                filtered_events = sorted(filtered_events, key=lambda x: (x['summary'], x['start']))
            else:  # "Date & Time"
                filtered_events = sorted(filtered_events, key=lambda x: x['start'])
            
            # Display filtered events
            if filtered_events:
                # Display filter terms being used
                if filter_text:
                    filter_terms = [term.strip() for term in filter_text.split(',') if term.strip()]
                    st.write("**Active filters:** ", ", ".join(filter_terms))
                
                st.write(f"### Found {len(filtered_events)} matching events:")
                
                if sort_order == "Date & Time":
                    # Group events by date
                    events_by_date = {}
                    for event in filtered_events:
                        date_str = event['start'].strftime('%Y-%m-%d')
                        if date_str not in events_by_date:
                            events_by_date[date_str] = []
                        events_by_date[date_str].append(event)
                    
                    # Display events grouped by date
                    for date_str, date_events in sorted(events_by_date.items()):
                        st.subheader(datetime.strptime(date_str, '%Y-%m-%d').strftime('%A, %B %d, %Y'))
                        for event in sorted(date_events, key=lambda x: x['start']):
                            event_text = (
                                f"**{event['summary']}**  \n"
                                f"Time: {event['start'].strftime('%I:%M %p')} - {event['end'].strftime('%I:%M %p')}  \n"
                                f"Location: {event.get('location', 'N/A')}"
                            )
                            if show_original:
                                event_text += f"\n\nOriginal text: {event['original_text']}"
                            st.markdown(event_text)
                            st.markdown("---")
                else:  # Group Name
                    current_group = None
                    for event in filtered_events:
                        if event['summary'] != current_group:
                            current_group = event['summary']
                            st.subheader(current_group)
                        
                        event_text = (
                            f"**{event['start'].strftime('%A, %B %d, %Y')}**  \n"
                            f"Time: {event['start'].strftime('%I:%M %p')} - {event['end'].strftime('%I:%M %p')}  \n"
                            f"Location: {event.get('location', 'N/A')}"
                        )
                        if show_original:
                            event_text += f"\n\nOriginal text: {event['original_text']}"
                        st.markdown(event_text)
                        st.markdown("---")
                
                # Generate CSV file for filtered events
                csv_data = create_google_calendar_csv(filtered_events)
                
                st.download_button(
                    label=f"Download {len(filtered_events)} events as Google Calendar CSV",
                    data=csv_data,
                    file_name="swimming_schedule_filtered.csv",
                    mime="text/csv"
                )
                
                st.write("""
                ### How to import to Google Calendar:
                1. Download the CSV file
                2. Go to [Google Calendar](https://calendar.google.com)
                3. Click the gear icon (Settings)
                4. Click 'Import & Export'
                5. Select the downloaded CSV file
                6. Choose the calendar to import to
                7. Click 'Import'
                """)
            else:
                st.warning("No events found matching your filter criteria.")
            
        except Exception as e:
            st.error(f"Error processing PDF: {e}")

if __name__ == "__main__":
    main()
