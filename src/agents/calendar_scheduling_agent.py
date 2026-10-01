import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from icalendar import Calendar
import urllib.request
import urllib.parse
import pytz

class CalendarSchedulingAgent:
    def __init__(self, calendar_url: str = None):
        # Load config
        self.calendar_config = self._load_calendar_config()
        self._validate_config()
        
        # Use provided URL from frontend
        self.calendar_url = calendar_url
        if not self.calendar_url:
            self.calendar_url = self.calendar_config.get('ical_url')
        
        self.local_timezone = pytz.timezone(self.calendar_config.get('timezone', 'Asia/Kolkata'))
        self.interview_duration = self.calendar_config.get('interview_duration_minutes', 60)
        self.buffer_minutes = self.calendar_config.get('buffer_minutes', 15)
        
        # Buffer is only needed between interviews in SAME panel
        self.slot_gap_minutes = self.buffer_minutes  # 15 min gap between interviews in same panel
        
        # Store last result for saving
        self.last_result = None
        
        print("✅ Calendar Agent - TIME ALLOCATION SCHEDULING")
        print(f"   📅 Using calendar URL: {self.calendar_url[:50]}..." if self.calendar_url else "   ⚠️ No calendar URL provided")
        print(f"   ⏱️  Interview: {self.interview_duration}min")
        print(f"   ⏳ Buffer between interviews: {self.buffer_minutes}min (only for multiple interviews in same panel)")

    def _load_calendar_config(self) -> Dict:
        """Load calendar configuration"""
        try:
            with open("config/calendar_config.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "timezone": "Asia/Kolkata",
                "interview_duration_minutes": 60,
                "buffer_minutes": 15,
                "work_hours_start": "09:00",
                "work_hours_end": "18:00",
                "work_days": [0, 1, 2, 3, 4]  # Monday to Friday
            }

    def _validate_config(self):
        """Validate configuration"""
        required = ['timezone', 'interview_duration_minutes', 'work_hours_start', 'work_hours_end']
        for field in required:
            if field not in self.calendar_config:
                raise Exception(f"Missing: {field}")
        
        # Validate work hours
        try:
            datetime.strptime(self.calendar_config['work_hours_start'], '%H:%M')
            datetime.strptime(self.calendar_config['work_hours_end'], '%H:%M')
        except ValueError:
            raise Exception("Work hours must be HH:MM format")

    async def schedule_interviews(self, ranking_results: Dict, calendar_url: str = None, interview_mode: str = "online") -> Dict:
        """Schedule interviews with rank-based priority"""
        print(f"\n🗓️  SCHEDULING INTERVIEWS")
        print(f"   ⏱️  Interview Duration: {self.interview_duration}min")
        print(f"   ⏳ Buffer between interviews: {self.buffer_minutes}min")
        print(f"   💻 Mode: {interview_mode}")
        print(f"   🏆 Priority: Highest rank gets earliest available slot")
        
        if calendar_url:
            self.calendar_url = calendar_url
        
        # Get ranked candidates - sort by rank (ascending, rank 1 is highest)
        ranking_report = ranking_results.get("ranking_report", {})
        ranked_candidates = ranking_report.get("ranked_candidates", [])
        
        # Sort candidates by rank
        if ranked_candidates:
            ranked_candidates = sorted(ranked_candidates, key=lambda x: x.get('rank', 999))
            print(f"   🎯 Candidates sorted by rank: {[c.get('rank') for c in ranked_candidates]}")
        
        if not ranked_candidates:
            print("   ⚠️ No candidates to schedule")
            result = {
                "scheduled_interviews": [],
                "status": "no_candidates"
            }
            self.last_result = result
            self._save_schedule(result)
            return result
        
        print(f"   📋 {len(ranked_candidates)} candidates to schedule (Rank order: {[c.get('rank') for c in ranked_candidates]})")
        
        # Get available slots
        if not self.calendar_url:
            print("   ⚠️  No calendar URL - using fallback slots")
            available_slots = self._generate_fallback_slots()
        else:
            print(f"   🔗 Using iCal URL")
            available_slots = await self._get_available_slots_from_calendar()
            
            if not available_slots:
                print("   ⚠️  No suitable slots found - using fallback slots")
                available_slots = self._generate_fallback_slots()
            else:
                print(f"   ✅ Found {len(available_slots)} available slots")
        
        # Sort slots by datetime (earliest first) and filter only available slots
        # FIX: Filter and properly sort slots by datetime
        available_slots = [slot for slot in available_slots if slot.get('is_available', False)]

        # Create a proper sorting function
        def sort_slots_by_datetime(slot):
            dt = slot.get('datetime')
            if dt and hasattr(dt, 'strftime'):
                return dt
            # Fallback: create datetime from date and time
            try:
                date_str = slot.get('date', '')
                time_str = slot.get('time', '')
                
                if not date_str or not time_str:
                    return datetime.max
                
                # Parse date
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Parse time (handle AM/PM)
                time_str_clean = time_str.strip()
                if 'AM' in time_str_clean.upper() or 'PM' in time_str_clean.upper():
                    time_obj = datetime.strptime(time_str_clean, "%I:%M %p")
                else:
                    time_obj = datetime.strptime(time_str_clean, "%H:%M")
                
                # Combine and localize
                combined = datetime.combine(date_obj.date(), time_obj.time())
                if self.local_timezone:
                    combined = self.local_timezone.localize(combined)
                
                return combined
            except Exception as e:
                print(f"   ⚠️ Could not parse slot datetime: {e}")
                return datetime.max

        available_slots = sorted(available_slots, key=sort_slots_by_datetime)

        # DEBUG: Show sorted order
        print(f"\n   🕐 SORTED SLOTS ORDER (Earliest → Latest):")
        for i, slot in enumerate(available_slots[:len(ranked_candidates) + 2]):  # Show enough for all candidates
            dt = slot.get('datetime')
            if hasattr(dt, 'strftime'):
                time_display = dt.strftime("%Y-%m-%d %H:%M")
            else:
                time_display = f"{slot['date']} {slot['time']}"
            
            print(f"   Slot {i}: {time_display} - Panel: {slot.get('panel_name', 'general')}")
                
        # DEBUG: Show slots details
        print(f"   🔍 DEBUG: We have {len(available_slots)} available slots")
        for i, slot in enumerate(available_slots[:10]):
            panel = slot.get('panel_name', 'general')
            duration = slot.get('duration_minutes', 0)
            print(f"   🔍 Slot {i}: {slot.get('date')} {slot.get('time')} ({duration}min) - Panel: {panel}")
        if len(available_slots) > 10:
            print(f"   🔍 ... and {len(available_slots) - 10} more slots")
        
        print(f"   🎯 Starting rank-based slot allocation...")
        
        # Schedule candidates by rank priority
        scheduled_interviews = []
        scheduled_count = 0
        unscheduled_candidates = []
        
        # For each candidate in rank order
        for candidate_index, candidate in enumerate(ranked_candidates):
            if candidate_index < len(available_slots):
                slot = available_slots[candidate_index]
                interview = await self._schedule_candidate(candidate, slot, interview_mode)
                scheduled_interviews.append(interview)
                scheduled_count += 1
                
                print(f"   ✅ Rank #{candidate.get('rank', 'N/A')}: {candidate['name']} → {slot['date']} {slot['time']} ({slot.get('panel_name')})")
            else:
                unscheduled_candidates.append(candidate['name'])
                print(f"   ❌ Rank #{candidate.get('rank', 'N/A')}: {candidate['name']} - No slot available")
        
        # Create result
        result = {
            "scheduled_interviews": scheduled_interviews,
            "unscheduled_candidates": unscheduled_candidates,
            "total_candidates": len(ranked_candidates),
            "scheduled_count": scheduled_count,
            "unscheduled_count": len(unscheduled_candidates),
            "scheduling_order": "by_rank"
        }
        
        # Check if all candidates were scheduled
        if scheduled_count == len(ranked_candidates):
            print(f"\n✅ SUCCESS: All {scheduled_count} candidates scheduled successfully by rank!")
            result["status"] = "complete"
            result["message"] = f"All {scheduled_count} candidates scheduled by rank priority"
        elif scheduled_count > 0:
            unscheduled_count = len(ranked_candidates) - scheduled_count
            print(f"\n⚠️ PARTIAL: {scheduled_count} candidates scheduled by rank. {unscheduled_count} still need slots.")
            result["status"] = "partial"
            result["scheduled_count"] = scheduled_count
            result["unscheduled_count"] = unscheduled_count
            result["message"] = f"Scheduled {scheduled_count} candidates by rank priority. {unscheduled_count} still need slots."
            result["frontend_action"] = {
                "type": "upload_calendar",
                "title": "Need More Calendar Slots",
                "message": f"Scheduled {scheduled_count} candidates by rank priority. {unscheduled_count} candidates still need time slots. Please upload a new calendar with available time slots.",
                "scheduled_so_far": scheduled_count,
                "remaining_to_schedule": unscheduled_count
            }
        else:
            print(f"\n❌ FAILED: No candidates could be scheduled - USING FALLBACK")
            fallback_slots = self._generate_fallback_slots()
            forced_interviews = []
            for i, candidate in enumerate(ranked_candidates[:5]):
                if i < len(fallback_slots):
                    interview = await self._schedule_candidate(candidate, fallback_slots[i], interview_mode)
                    forced_interviews.append(interview)
                    print(f"   ⚡ Rank #{candidate.get('rank', 'N/A')}: {candidate['name']} → {fallback_slots[i]['date']} {fallback_slots[i]['time']}")
            
            if forced_interviews:
                result["scheduled_interviews"] = forced_interviews
                result["status"] = "partial"
                result["scheduled_count"] = len(forced_interviews)
                result["unscheduled_count"] = len(ranked_candidates) - len(forced_interviews)
                result["message"] = f"Used fallback slots to schedule {len(forced_interviews)} candidates by rank."
                result["frontend_action"] = {
                    "type": "upload_calendar",
                    "title": "Need More Calendar Slots",
                    "message": f"Scheduled {len(forced_interviews)} candidates. {len(ranked_candidates) - len(forced_interviews)} candidates still need time slots. Please upload a new calendar with available time slots.",
                    "scheduled_so_far": len(forced_interviews),
                    "remaining_to_schedule": len(ranked_candidates) - len(forced_interviews)
                }
                print(f"\n✅ RECOVERY: Scheduled {len(forced_interviews)} candidates using fallback slots")
            else:
                result["status"] = "no_slots"
                result["message"] = "No available time slots found in the calendar."
                result["frontend_action"] = {
                    "type": "upload_calendar",
                    "title": "No Available Time Slots",
                    "message": "No available time slots found in the calendar. Please upload a calendar with available time slots."
                }
        
        # Store result for saving
        self.last_result = result
        self._save_schedule(result)
        self._display_final_schedule(scheduled_interviews, interview_mode)
        
        return result

    async def update_calendar_and_continue(self, new_calendar_url: str, interview_mode: str = "online") -> Dict:
        """RESCHEDULE ALL candidates with new calendar URL - WITH RANK PRIORITY"""
        print(f"\n🔄 RESCHEDULING ALL CANDIDATES WITH NEW CALENDAR")
        print(f"   🔗 New calendar URL: {new_calendar_url[:50]}...")
        print(f"   🏆 Priority: Scheduling by rank order")
        print(f"   ⏱️  Interview: {self.interview_duration}min, Buffer: {self.buffer_minutes}min between interviews")
        
        try:
            file_path = "output/candidate_ranking_report.json"
            
            if not os.path.exists(file_path):
                file_path = "../output/candidate_ranking_report.json"
                if not os.path.exists(file_path):
                    return {
                        "status": "error",
                        "message": "Candidate ranking file not found",
                        "scheduled_interviews": []
                    }
            
            # Load candidates
            with open(file_path, "r", encoding='utf-8') as f:
                ranking_report = json.load(f)
            
            ranked_candidates = ranking_report.get("ranked_candidates", [])
            
            if not ranked_candidates:
                try:
                    with open("output/screening_results.json", "r", encoding='utf-8') as f:
                        screening_data = json.load(f)
                    eligible_candidates = screening_data.get("eligible_candidates", [])
                    ranked_candidates = []
                    for i, candidate in enumerate(eligible_candidates[:5], 1):
                        candidate_info = candidate.get("candidate_info", {})
                        ranked_candidates.append({
                            "name": candidate_info.get("name", f"Candidate {i}"),
                            "rank": i,
                            "comprehensive_score": candidate.get("overall_score", 5.0),
                            "email": candidate_info.get("email", "")
                        })
                    print(f"   🔄 Using {len(ranked_candidates)} candidates from screening results")
                except Exception as e:
                    print(f"   ❌ Could not load screening results: {e}")
                    return {
                        "status": "error",
                        "message": "No candidates found",
                        "scheduled_interviews": []
                    }
            
            # Sort candidates by rank
            ranked_candidates = sorted(ranked_candidates, key=lambda x: x.get('rank', 999))
            print(f"   📋 {len(ranked_candidates)} candidates to schedule (Rank order: {[c.get('rank') for c in ranked_candidates]})")
            
            # Get slots from new calendar
            self.calendar_url = new_calendar_url
            available_slots = await self._get_available_slots_from_calendar()
            
            if not available_slots:
                print("   ⚠️ No slots in new calendar - using fallback")
                available_slots = self._generate_fallback_slots()
            else:
                print(f"   ✅ Found {len(available_slots)} slots in new calendar")
            
            # Filter and sort slots
                        # FIX: Filter and properly sort slots by datetime
            available_slots = [slot for slot in available_slots if slot.get('is_available', False)]

            # Create a proper sorting function
            def sort_slots_by_datetime(slot):
                dt = slot.get('datetime')
                if dt and hasattr(dt, 'strftime'):
                    return dt
                # Fallback: create datetime from date and time
                try:
                    date_str = slot.get('date', '')
                    time_str = slot.get('time', '')
                    
                    if not date_str or not time_str:
                        return datetime.max
                    
                    # Parse date
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    # Parse time (handle AM/PM)
                    time_str_clean = time_str.strip()
                    if 'AM' in time_str_clean.upper() or 'PM' in time_str_clean.upper():
                        time_obj = datetime.strptime(time_str_clean, "%I:%M %p")
                    else:
                        time_obj = datetime.strptime(time_str_clean, "%H:%M")
                    
                    # Combine and localize
                    combined = datetime.combine(date_obj.date(), time_obj.time())
                    if self.local_timezone:
                        combined = self.local_timezone.localize(combined)
                    
                    return combined
                except Exception as e:
                    print(f"   ⚠️ Could not parse slot datetime: {e}")
                    return datetime.max

            available_slots = sorted(available_slots, key=sort_slots_by_datetime)

            # DEBUG: Show sorted order
            print(f"\n   🕐 SORTED SLOTS ORDER (Earliest → Latest):")
            for i, slot in enumerate(available_slots[:len(ranked_candidates) + 2]):  # Show enough for all candidates
                dt = slot.get('datetime')
                if hasattr(dt, 'strftime'):
                    time_display = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    time_display = f"{slot['date']} {slot['time']}"
                
                print(f"   Slot {i}: {time_display} - Panel: {slot.get('panel_name', 'general')}")
            
            # Schedule ALL candidates by rank priority
            scheduled_interviews = []
            unscheduled_candidates = []
            
            print(f"\n   🎯 SCHEDULING IN RANK ORDER:")
            for candidate_index, candidate in enumerate(ranked_candidates):
                if candidate_index < len(available_slots):
                    slot = available_slots[candidate_index]
                    interview = await self._schedule_candidate(candidate, slot, interview_mode)
                    scheduled_interviews.append(interview)
                    print(f"   ✅ Rank #{candidate.get('rank', 'N/A')}: {candidate['name']} → {slot['date']} {slot['time']} ({slot.get('panel_name')})")
                else:
                    unscheduled_candidates.append(candidate['name'])
                    print(f"   ❌ Rank #{candidate.get('rank', 'N/A')}: {candidate['name']} - No slot available")
            
            # Create result
            result = {
                "scheduled_interviews": scheduled_interviews,
                "unscheduled_candidates": unscheduled_candidates,
                "total_candidates": len(ranked_candidates),
                "scheduled_count": len(scheduled_interviews),
                "unscheduled_count": len(unscheduled_candidates),
                "calendar_used": new_calendar_url[:100] + "..." if len(new_calendar_url) > 100 else new_calendar_url,
                "scheduling_order": "by_rank"
            }
            
            # Save results
            self._save_schedule({"scheduled_interviews": scheduled_interviews})
            
            # Show final schedule
            self._display_final_schedule(scheduled_interviews, interview_mode)
            
            # Add status
            if len(scheduled_interviews) == len(ranked_candidates):
                result["status"] = "complete"
                result["message"] = f"✅ Successfully scheduled all {len(scheduled_interviews)} candidates by rank!"
                print(f"\n✅ SUCCESS: All {len(scheduled_interviews)} candidates scheduled by rank priority!")
            elif scheduled_interviews:
                result["status"] = "partial"
                result["message"] = f"Scheduled {len(scheduled_interviews)} candidates by rank. {len(ranked_candidates) - len(scheduled_interviews)} still need slots."
                result["frontend_action"] = {
                    "type": "upload_calendar",
                    "title": "Need More Calendar Slots",
                    "message": f"Scheduled {len(scheduled_interviews)} candidates by rank priority. {len(ranked_candidates) - len(scheduled_interviews)} candidates still need time slots.",
                    "scheduled_so_far": len(scheduled_interviews),
                    "remaining_to_schedule": len(ranked_candidates) - len(scheduled_interviews)
                }
                print(f"\n⚠️ PARTIAL: {len(scheduled_interviews)} scheduled by rank, {len(ranked_candidates) - len(scheduled_interviews)} unscheduled")
            else:
                result["status"] = "no_slots"
                result["message"] = "No available time slots found."
                print(f"\n❌ FAILED: No candidates scheduled")
            
            return result
                    
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Error: {str(e)}",
                "scheduled_interviews": []
            }

    async def _get_available_slots_from_calendar(self) -> List[Dict]:
        """Get slots from iCal calendar"""
        if not self.calendar_url:
            return []
            
        print(f"   🔗 Reading iCal data from: {self.calendar_url[:50]}...")
        
        try:
            if self.calendar_url.startswith('file://'):
                file_path = urllib.parse.unquote(self.calendar_url[7:])
                print(f"   📁 Reading local file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    calendar_data = f.read().encode('utf-8')
            elif self.calendar_url.startswith('http'):
                req = urllib.request.Request(
                    self.calendar_url,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                response = urllib.request.urlopen(req, timeout=10)
                calendar_data = response.read()
            else:
                print(f"   📁 Reading local file: {self.calendar_url}")
                with open(self.calendar_url, 'r', encoding='utf-8') as f:
                    calendar_data = f.read().encode('utf-8')
            
            if b'BEGIN:VCALENDAR' not in calendar_data:
                print("   ⚠️ Not a valid iCal format")
                return []
                
            cal = Calendar.from_ical(calendar_data)
            
            # Get all events and parse them
            all_events = []
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = self._parse_calendar_event(component)
                    if event:
                        all_events.append(event)
            
            print(f"   📊 Found {len(all_events)} events in calendar")
            
            # Generate interview slots from events
            available_slots = self._generate_interview_slots_from_events(all_events)
            
            print(f"   ✅ Generated {len(available_slots)} interview slots")
            return available_slots
            
        except Exception as e:
            print(f"   ❌ Error reading calendar: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_calendar_event(self, event) -> Optional[Dict]:
        """Parse calendar event"""
        try:
            summary = str(event.get('SUMMARY', '')).strip()
            description = str(event.get('DESCRIPTION', ''))
            
            start_time = event.get('DTSTART').dt
            end_time = event.get('DTEND').dt
            
            # Handle timezone
            if isinstance(start_time, datetime):
                if start_time.tzinfo is not None:
                    start_dt = start_time.astimezone(self.local_timezone)
                    end_dt = end_time.astimezone(self.local_timezone)
                else:
                    start_dt = self.local_timezone.localize(start_time)
                    end_dt = self.local_timezone.localize(end_time)
            else:
                start_dt = self.local_timezone.localize(datetime.combine(start_time, datetime.min.time()))
                end_dt = self.local_timezone.localize(datetime.combine(end_time, datetime.min.time()))
            
            # Check if it's a future event
            now = datetime.now(self.local_timezone)
            if start_dt < now:
                return None
            
            # Calculate duration
            total_duration = (end_dt - start_dt).total_seconds() / 60
            
            # Extract panel name from summary
            panel_name = "general"
            summary_lower = summary.lower()
            
            # Look for panel patterns
            panel_patterns = [
                r'panel\s*([A-Za-z0-9]+)',
                r'([A-Za-z0-9]+)\s*panel',
                r'interview\s*([A-Za-z0-9]+)',
                r'([A-Za-z0-9]+)\s*interview',
                r'slot\s*([A-Za-z0-9]+)'
            ]
            
            for pattern in panel_patterns:
                match = re.search(pattern, summary_lower, re.IGNORECASE)
                if match:
                    panel_name = match.group(1).upper()
                    break
            
            # Determine if event is busy or free
            is_available = False
            
            # Check various indicators
            free_indicators = ['free', 'available', 'open slot', 'interview slot', 'open', 'slot', 'free time', 'panel', 'interview time', 'interview window']
            busy_indicators = ['busy', 'occupied', 'meeting', 'call', 'appointment', 'scheduled', 'out of office', 'ooo']
            
            if any(indicator in summary_lower for indicator in free_indicators):
                is_available = True
            elif any(indicator in summary_lower for indicator in busy_indicators):
                is_available = False
            
            # Check if it's a panel (panels are for interviews)
            if 'panel' in summary_lower:
                is_available = True
            
            # Check transparency property
            transparency = str(event.get('TRANSP', '')).upper()
            if transparency == 'TRANSPARENT':
                is_available = True
            elif transparency == 'OPAQUE':
                is_available = False
            
            # Generate meet link if available
            meet_link = ""
            if is_available:
                meet_pattern = r'https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}'
                if description:
                    match = re.search(meet_pattern, description, re.IGNORECASE)
                    if match:
                        meet_link = match.group(0)
                
                if not meet_link:
                    location = str(event.get('LOCATION', ''))
                    match = re.search(meet_pattern, location, re.IGNORECASE)
                    if match:
                        meet_link = match.group(0)
                        
                if not meet_link:
                    meet_link = f"https://meet.google.com/cal-{start_dt.strftime('%Y%m%d-%H%M')}"
            
            return {
                "date": start_dt.strftime("%Y-%m-%d"),
                "time": start_dt.strftime("%I:%M %p"),
                "datetime": start_dt,
                "end_datetime": end_dt,
                "duration_minutes": total_duration,
                "summary": summary,
                "description": description,
                "calendar_source": "google_calendar",
                "slot_id": f"slot_{start_dt.strftime('%Y%m%d_%H%M')}",
                "meet_link": meet_link,
                "panel_name": panel_name,
                "is_available": is_available,
                "sort_key": start_dt,
                "original_duration": total_duration
            }
            
        except Exception as e:
            print(f"   ⚠️ Error parsing calendar event: {e}")
            return None

    def _generate_interview_slots_from_events(self, events: List[Dict]) -> List[Dict]:
        """Generate interview slots from calendar events - TREAT EACH PANEL SEPARATELY"""
        slots = []
        
        # Separate free events by panel
        free_events_by_panel = {}
        for event in events:
            if event.get('is_available', False):
                panel_name = event.get('panel_name', 'unknown')
                if panel_name not in free_events_by_panel:
                    free_events_by_panel[panel_name] = []
                free_events_by_panel[panel_name].append(event)
        
        print(f"   🔍 Found {len(free_events_by_panel)} different panels with availability")
        
        # Process each panel separately
        for panel_name, panel_events in free_events_by_panel.items():
            print(f"   📋 Processing Panel {panel_name}: {len(panel_events)} free event(s)")
            
            # Sort events by start time for this panel
            panel_events.sort(key=lambda x: x['datetime'])
            
            # Process each event for this panel
            for event_index, event in enumerate(panel_events):
                event_start = event['datetime']
                event_end = event['end_datetime']
                event_duration = event['duration_minutes']
                
                print(f"     📅 {event['date']}: {event_start.strftime('%H:%M')}-{event_end.strftime('%H:%M')} "
                      f"({event_duration:.0f}min)")
                
                # Generate slots for this event
                event_slots = self._generate_slots_for_event(
                    event_start, event_end, panel_name, event['date'], event.get('meet_link', '')
                )
                
                slots.extend(event_slots)
        
        # Sort all slots by time
        # FIX: Sort all slots by datetime GLOBALLY
        if slots:
            # DEBUG: Show before sorting
            print(f"\n   🔍 DEBUG - Slots BEFORE global sorting:")
            for i, slot in enumerate(slots[:5]):
                dt = slot.get('datetime')
                if hasattr(dt, 'strftime'):
                    print(f"   {i}: {slot['date']} {slot['time']} (Panel: {slot['panel_name']}) - Datetime: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    print(f"   {i}: {slot['date']} {slot['time']} (Panel: {slot['panel_name']})")
            
            # Sort by datetime
            slots.sort(key=lambda x: x.get('datetime') if x.get('datetime') else datetime.max)
            
            # DEBUG: Show after sorting
            print(f"\n   🔍 DEBUG - Slots AFTER global sorting (first 10):")
            for i, slot in enumerate(slots[:10]):
                dt = slot.get('datetime')
                if hasattr(dt, 'strftime'):
                    print(f"   {i}: {slot['date']} {slot['time']} (Panel: {slot['panel_name']}) - Datetime: {dt.strftime('%Y-%m-%d %H:%M')}")
                else:
                    print(f"   {i}: {slot['date']} {slot['time']} (Panel: {slot['panel_name']})")

        print(f"   📊 Generated {len(slots)} total interview slots across all panels")
        return slots

    def _generate_slots_for_event(self, event_start: datetime, event_end: datetime, 
                                panel_name: str, date_str: str, original_meet_link: str = "") -> List[Dict]:
        """Generate interview slots for a specific event in a panel"""
        slots = []
        
        event_duration = (event_end - event_start).total_seconds() / 60
        
        # Skip if event is too short
        if event_duration < self.interview_duration:
            print(f"       ⚠️  Too short for interview (need {self.interview_duration}min, have {event_duration:.0f}min)")
            return slots
        
        # Calculate how many interviews can fit
        # For 1 interview: need 60min
        # For 2+ interviews: need 60min + 15min buffer + 60min for next, etc.
        
        current_time = event_start
        interview_count = 0
        
        while True:
            # Calculate remaining time
            time_remaining = (event_end - current_time).total_seconds() / 60
            
            # Check if we have enough time for at least one interview
            if time_remaining < self.interview_duration:
                break
            
            # This will be interview number (interview_count + 1)
            is_first_in_series = (interview_count == 0)
            
            # Calculate end time for this interview
            interview_end = current_time + timedelta(minutes=self.interview_duration)
            
            # Check if there will be another interview after this one
            time_after_this_interview = (event_end - interview_end).total_seconds() / 60
            will_have_next_interview = (time_after_this_interview >= self.interview_duration)
            
            # Create slot
            slot_id = f"slot_{panel_name}_{current_time.strftime('%Y%m%d_%H%M')}"
            
            if original_meet_link:
                meet_link = original_meet_link
            else:
                meet_link = f"https://meet.google.com/{panel_name.lower()}-{current_time.strftime('%Y%m%d-%H%M')}"
            
            slot = {
                "date": date_str,
                "time": current_time.strftime("%I:%M %p"),
                "datetime": current_time,
                "end_datetime": interview_end,
                "duration_minutes": self.interview_duration,
                "summary": f"Interview Slot - Panel {panel_name}",
                "calendar_source": "google_calendar",
                "slot_id": slot_id,
                "meet_link": meet_link,
                "panel_name": panel_name,
                "is_available": True,
                "sort_key": current_time,
                "interview_number": interview_count + 1,
                "has_buffer_after": will_have_next_interview  # Only buffer if there's another interview
            }
            
            slots.append(slot)
            print(f"       🎯 Slot {interview_count + 1}: {current_time.strftime('%H:%M')}-{interview_end.strftime('%H:%M')}")
            
            # Move to next possible slot time
            if will_have_next_interview:
                # Add buffer for next interview
                current_time = interview_end + timedelta(minutes=self.buffer_minutes)
                print(f"         ⏳ Adding {self.buffer_minutes}min buffer before next interview")
            else:
                # No more interviews can fit
                break
            
            interview_count += 1
        
        print(f"       ✅ Can fit {len(slots)} interview(s) in this time slot")
        return slots

    def _generate_fallback_slots(self) -> List[Dict]:
        """Generate fallback slots"""
        print("   🔄 Generating fallback slots...")
        
        today = datetime.now(self.local_timezone)
        slots = []
        
        # Generate slots for today + next 7 days
        for day_offset in range(0, 7):
            slot_date = today + timedelta(days=day_offset)
            date_str = slot_date.strftime("%Y-%m-%d")
            
            # Skip weekends
            if slot_date.weekday() >= 5:
                continue
            
            # Generate slots per day
            time_slots = [
                (9, 0, "A"),
                (10, 0, "B"),
                (11, 0, "C"),
                (14, 0, "A"),
                (15, 0, "B"),
                (16, 0, "C")
            ]
            
            for hour, minute, panel in time_slots:
                current_time = slot_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Make sure it's in the future
                if current_time < today:
                    continue
                
                interview_end = current_time + timedelta(minutes=self.interview_duration)
                
                slots.append({
                    "date": date_str,
                    "time": current_time.strftime("%I:%M %p"),
                    "datetime": current_time,
                    "end_datetime": interview_end,
                    "duration_minutes": self.interview_duration,
                    "summary": f"Fallback Interview Slot - Panel {panel}",
                    "calendar_source": "fallback",
                    "slot_id": f"fallback_{panel}_{date_str}_{hour:02d}{minute:02d}",
                    "meet_link": f"https://meet.google.com/fallback-{panel}-{date_str}-{hour:02d}{minute:02d}",
                    "panel_name": panel,
                    "is_available": True,
                    "sort_key": current_time,
                    "has_buffer_after": False
                })
        
        print(f"   ✅ Generated {len(slots)} fallback slots")
        return slots

    async def _schedule_candidate(self, candidate: Dict, slot: Dict, interview_mode: str = "online") -> Dict:
        """Schedule candidate"""
        candidate_email = candidate.get("email", "")
        if not candidate_email:
            candidate_email = await self._get_candidate_email(candidate["name"])
        
        return {
            "candidate_name": candidate["name"],
            "candidate_email": candidate_email,
            "rank": candidate.get("rank", 0),
            "score": candidate.get("comprehensive_score", candidate.get("score", 0)),
            "interview_date": slot["date"],
            "interview_time": slot["time"],
            "event_name": slot.get("summary", ""),
            "duration_minutes": self.interview_duration,
            "buffer_minutes": self.buffer_minutes if slot.get("has_buffer_after", False) else 0,
            "status": "scheduled",
            "scheduled_at": datetime.now(self.local_timezone).isoformat(),
            "calendar_source": slot.get("calendar_source", "unknown"),
            "interview_mode": interview_mode,
            "meeting_link": slot.get("meet_link", ""),
            "meet_source": "calendar",
            "slot_id": slot.get("slot_id", ""),
            "panel_name": slot.get("panel_name", "unknown"),
            "has_buffer": slot.get("has_buffer_after", False)
        }

    async def _get_candidate_email(self, candidate_name: str) -> str:
        """Get candidate email"""
        try:
            with open("output/screening_results.json", "r", encoding='utf-8') as f:
                data = json.load(f)
            for candidate_data in data.get("eligible_candidates", []):
                if candidate_data.get("candidate_info", {}).get("name") == candidate_name:
                    return candidate_data.get("candidate_info", {}).get("email", "")
            return ""
        except:
            return ""

    def _save_schedule(self, schedule: Dict):
        """Save schedule"""
        os.makedirs("output", exist_ok=True)
        
        with open("output/interview_schedule.json", "w", encoding='utf-8') as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False, default=str)
        
        print("✅ Schedule saved to output/interview_schedule.json")

    def _display_final_schedule(self, scheduled_interviews: List[Dict], interview_mode: str = "online"):
        """Display final schedule with rank and panel information"""
        if not scheduled_interviews:
            print("   📭 No interviews scheduled")
            return
        
        print(f"\n📅 FINAL SCHEDULE ({len(scheduled_interviews)} interviews):")
        print("   ──────────────────────────────────")
        
        # Sort interviews by date and time
        scheduled_interviews.sort(key=lambda x: (
            x["interview_date"], 
            datetime.strptime(x["interview_time"], "%I:%M %p").strftime("%H:%M") if "AM" in x["interview_time"] or "PM" in x["interview_time"] else x["interview_time"]
        ))
        
        # Group by date
        by_date = {}
        for interview in scheduled_interviews:
            date = interview["interview_date"]
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(interview)
        
        # Sort dates and display
        for date in sorted(by_date.keys()):
            print(f"   📅 {date}:")
            daily = by_date[date]
            daily.sort(key=lambda x: datetime.strptime(x["interview_time"], "%I:%M %p") if "AM" in x["interview_time"] or "PM" in x["interview_time"] else x["interview_time"])
            
            for interview in daily:
                name = interview["candidate_name"]
                time = interview["interview_time"]
                rank = interview.get("rank", "N/A")
                panel = interview.get("panel_name", "general")
                buffer = " (+15min buffer)" if interview.get("has_buffer", False) else ""
                print(f"     • {time} - {name} [Rank #{rank}, Panel: {panel}]{buffer}")
            print()
        
        print(f"   📊 Total scheduled: {len(scheduled_interviews)}")
        
        # Show panel distribution
        panels = [i.get("panel_name", "general") for i in scheduled_interviews]
        if panels:
            panel_counts = {}
            for panel in panels:
                panel_counts[panel] = panel_counts.get(panel, 0) + 1
            
            print(f"   🎯 Panel distribution:")
            for panel, count in panel_counts.items():
                print(f"        • Panel {panel}: {count} interview(s)")
        
        # Show rank distribution summary
        ranks = [i.get("rank", 0) for i in scheduled_interviews]
        if ranks:
            print(f"   🏆 Rank distribution: {sorted(ranks)}")