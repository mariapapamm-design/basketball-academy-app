import io
import uuid
import calendar
import streamlit as st
import pandas as pd

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from supabase import create_client

APP_NAME = "Ταυροι Καλαμαριας Coaches 🏀"
PHOTO_BUCKET = "player-photos"

TEAMS = [
    "Παμπαίδων Α’",
    "2012–2013 Β’",
    "Junior NBA",
    "2014–2015 Α’",
    "2014–2015 Β’",
    "2016–2017 Α’",
    "2016–2017 Β’",
    "2018",
    "2019–2020–2021",
    "Κορίτσια",
    "Ανδρικό",
]

JERSEY_SIZES = [
    "6", "8", "10", "12", "14", "16",
    "XS", "S", "M", "L", "XL", "XXL",
]

GREEK_MONTHS = {
    1: "Ιανουάριος",
    2: "Φεβρουάριος",
    3: "Μάρτιος",
    4: "Απρίλιος",
    5: "Μάιος",
    6: "Ιούνιος",
    7: "Ιούλιος",
    8: "Αύγουστος",
    9: "Σεπτέμβριος",
    10: "Οκτώβριος",
    11: "Νοέμβριος",
    12: "Δεκέμβριος",
}

st.set_page_config(
    page_title="Ταυροι Καλαμαριας Coaches",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# ΒΑΣΙΚΑ HELPERS
# ============================================================

def set_flash(message, level="success"):
    st.session_state["_flash_message"] = message
    st.session_state["_flash_level"] = level


def show_flash():
    message = st.session_state.pop("_flash_message", None)
    level = st.session_state.pop("_flash_level", "success")

    if not message:
        return

    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "info":
        st.info(message)
    else:
        st.success(message)


def format_date(value):
    if not value:
        return "—"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def format_money(value):
    try:
        return f"{float(value):.2f} €".replace(".", ",")
    except Exception:
        return "—"


def month_start(value):
    d = pd.to_datetime(value).date()
    return date(d.year, d.month, 1)


def month_label(value):
    d = pd.to_datetime(value).date()
    return f"{GREEK_MONTHS[d.month]} {d.year}"


def month_options(center=None, months_back=24, months_forward=36):
    if center is None:
        center = date.today().replace(day=1)
    else:
        center = month_start(center)

    start = center - relativedelta(months=months_back)
    return [
        start + relativedelta(months=i)
        for i in range(months_back + months_forward + 1)
    ]


def safe_date_with_day(year, month, day):
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


# ============================================================
# SUPABASE / AUTH
# ============================================================

def get_config():
    try:
        return (
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_PUBLISHABLE_KEY"],
            st.secrets["SUPABASE_SECRET_KEY"],
        )
    except Exception:
        st.error(
            "Λείπουν τα Supabase secrets. "
            "Χρειάζονται SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY και SUPABASE_SECRET_KEY."
        )
        st.stop()


SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY = get_config()


def public_client():
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)


def admin_client():
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def get_user_client():
    if "sb" not in st.session_state:
        st.session_state.sb = public_client()
    return st.session_state.sb


def logout():
    try:
        get_user_client().auth.sign_out()
    except Exception:
        pass

    for key in ["sb", "user", "profile"]:
        st.session_state.pop(key, None)

    st.rerun()


def load_profile(user_id):
    sb = get_user_client()
    result = (
        sb.table("profiles")
        .select("id,email,full_name,role,active,can_view_payments")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data


def require_login():
    if "user" not in st.session_state:
        st.title(APP_NAME)
        st.subheader("Είσοδος προπονητή")

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Κωδικός", type="password")
            submitted = st.form_submit_button(
                "Σύνδεση",
                use_container_width=True,
            )

        if submitted:
            try:
                sb = public_client()
                response = sb.auth.sign_in_with_password(
                    {
                        "email": email.strip(),
                        "password": password,
                    }
                )

                if not response.user:
                    st.error("Δεν ήταν δυνατή η σύνδεση.")
                    st.stop()

                st.session_state.sb = sb
                st.session_state.user = response.user

                profile = load_profile(response.user.id)

                if not profile or not profile.get("active", False):
                    try:
                        sb.auth.sign_out()
                    except Exception:
                        pass

                    st.session_state.pop("user", None)
                    st.session_state.pop("sb", None)
                    st.error("Ο λογαριασμός δεν έχει ενεργή πρόσβαση.")
                    st.stop()

                st.session_state.profile = profile
                st.rerun()

            except Exception:
                st.error("Λάθος email/κωδικός ή μη εγκεκριμένος λογαριασμός.")

        st.stop()

    if "profile" not in st.session_state:
        profile = load_profile(st.session_state.user.id)

        if not profile or not profile.get("active", False):
            logout()

        st.session_state.profile = profile


def role_is_admin():
    return st.session_state.profile.get("role") == "admin"


def can_access_payments():
    return role_is_admin() or bool(
        st.session_state.profile.get("can_view_payments", False)
    )


# ============================================================
# STORAGE / ΦΩΤΟΓΡΑΦΙΕΣ
# ============================================================

def ensure_photo_bucket():
    if st.session_state.get("_photo_bucket_checked"):
        return

    try:
        admin = admin_client()
        buckets = admin.storage.list_buckets()

        names = []
        for b in buckets or []:
            if isinstance(b, dict):
                names.append(b.get("name") or b.get("id"))
            else:
                names.append(getattr(b, "name", None) or getattr(b, "id", None))

        if PHOTO_BUCKET not in names:
            admin.storage.create_bucket(
                PHOTO_BUCKET,
                options={
                    "public": False,
                    "allowed_mime_types": [
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                    ],
                    "file_size_limit": 5 * 1024 * 1024,
                },
            )

        st.session_state["_photo_bucket_checked"] = True
    except Exception:
        # Δεν σταματάμε όλη την εφαρμογή αν το Storage έχει προσωρινό θέμα.
        pass


def upload_player_photo(player_id, uploaded_file):
    if uploaded_file is None:
        return None

    ensure_photo_bucket()

    ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else "jpg"
    if ext == "jpeg":
        ext = "jpg"

    path = f"{player_id}/{uuid.uuid4().hex}.{ext}"
    content_type = uploaded_file.type or "image/jpeg"

    admin_client().storage.from_(PHOTO_BUCKET).upload(
        path=path,
        file=uploaded_file.getvalue(),
        file_options={
            "content-type": content_type,
            "cache-control": "3600",
            "upsert": "false",
        },
    )
    return path


def remove_player_photo(path):
    if not path:
        return
    try:
        admin_client().storage.from_(PHOTO_BUCKET).remove([path])
    except Exception:
        pass


def signed_photo_url(path):
    if not path:
        return None

    try:
        response = (
            admin_client()
            .storage
            .from_(PHOTO_BUCKET)
            .create_signed_url(path, 3600)
        )

        if isinstance(response, dict):
            return (
                response.get("signedURL")
                or response.get("signedUrl")
                or response.get("signed_url")
            )

        return getattr(response, "signed_url", None)
    except Exception:
        return None


def show_player_photo(player, width=52):
    url = signed_photo_url(player.get("photo_path"))
    if url:
        st.image(url, width=width)
    else:
        st.markdown("👤")


# ============================================================
# DATA HELPERS
# ============================================================

def get_players(active_only=True):
    sb = get_user_client()
    query = sb.table("players").select("*").order("full_name")

    if active_only:
        query = query.eq("active", True)

    return query.execute().data or []


def player_short_name(player):
    number = (player.get("jersey_number") or "").strip()
    if number:
        return f"#{number} {player.get('full_name')}"
    return player.get("full_name")


def searchable_player_select(label, players, key, include_all=False, index=0):
    options = players[:]

    if include_all:
        labels = ["Όλοι οι παίκτες"] + [player_short_name(p) for p in options]
        selected = st.selectbox(
            label,
            labels,
            index=index,
            key=key,
            filter_mode="contains",
        )
        if selected == "Όλοι οι παίκτες":
            return None
        return options[labels.index(selected) - 1]

    labels = [player_short_name(p) for p in options]
    if not labels:
        return None

    selected = st.selectbox(
        label,
        labels,
        index=min(index, len(labels) - 1),
        key=key,
        filter_mode="contains",
    )
    return options[labels.index(selected)]


def duplicate_player_exists(full_name, birth_date, exclude_id=None):
    normalized = full_name.strip().casefold()
    for p in get_players(active_only=False):
        if exclude_id and p["id"] == exclude_id:
            continue
        if (
            (p.get("full_name") or "").strip().casefold() == normalized
            and str(p.get("birth_date") or "") == str(birth_date)
        ):
            return True
    return False


def get_all_attendance():
    return (
        get_user_client()
        .table("attendance")
        .select(
            "id,player_id,training_date,present,recorded_by,"
            "players(full_name,team,jersey_number,photo_path),"
            "profiles(full_name)"
        )
        .order("training_date")
        .limit(10000)
        .execute()
        .data
        or []
    )


def get_team_attendance(team):
    rows = []
    for r in get_all_attendance():
        pdata = r.get("players") or {}
        if (pdata.get("team") or "Χωρίς τμήμα") == team:
            rows.append(r)
    return rows


def attendance_matrix(players, attendance_rows, start_date=None, end_date=None):
    filtered = []

    for r in attendance_rows:
        d = pd.to_datetime(r.get("training_date")).date()
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        filtered.append(r)

    training_dates = sorted(
        {pd.to_datetime(r.get("training_date")).date() for r in filtered}
    )

    lookup = {
        (r.get("player_id"), pd.to_datetime(r.get("training_date")).date()): r.get("present")
        for r in filtered
    }

    output = []

    for p in players:
        row = {
            "Νο": p.get("jersey_number") or "—",
            "Ονοματεπώνυμο": p.get("full_name"),
        }

        present_count = 0
        absent_count = 0

        for d in training_dates:
            value = lookup.get((p["id"], d), None)

            if value is True:
                row[d.strftime("%d/%m")] = "✅"
                present_count += 1
            elif value is False:
                row[d.strftime("%d/%m")] = "❌"
                absent_count += 1
            else:
                row[d.strftime("%d/%m")] = "—"

        total = present_count + absent_count
        row["Παρουσίες"] = present_count
        row["Απουσίες"] = absent_count
        row["Ποσοστό"] = (
            f"{round((present_count / total) * 100, 1)}%"
            if total
            else "—"
        )

        output.append(row)

    return pd.DataFrame(output), training_dates


def excel_bytes_from_dataframe(df, sheet_name="Παρουσίες", title=None):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df.copy()

        # Τα emoji δεν είναι ιδανικά σε όλες τις εγκαταστάσεις Excel.
        export_df = export_df.replace(
            {
                "✅": "ΠΑΡΩΝ",
                "❌": "ΑΠΩΝ",
            }
        )

        startrow = 2 if title else 0
        export_df.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name[:31],
            startrow=startrow,
        )

        workbook = writer.book
        worksheet = writer.sheets[sheet_name[:31]]

        header_format = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        title_format = workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
            }
        )

        if title:
            worksheet.write(0, 0, title, title_format)

        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(startrow, col_num, value, header_format)

        for i, col in enumerate(export_df.columns):
            max_len = max(
                len(str(col)),
                export_df[col].astype(str).map(len).max() if not export_df.empty else 0,
            )
            worksheet.set_column(i, i, min(max(max_len + 2, 10), 30))

        worksheet.freeze_panes(startrow + 1, 0)

    return output.getvalue()


# ============================================================
# ΠΛΗΡΩΜΕΣ HELPERS
# ============================================================

def get_all_payments():
    return (
        get_user_client()
        .table("payments")
        .select(
            "id,player_id,amount,paid_on,note,created_at,"
            "coverage_month,payment_batch_id,recorded_by,"
            "profiles(full_name)"
        )
        .order("paid_on", desc=True)
        .limit(10000)
        .execute()
        .data
        or []
    )


def player_payment_status(player_id, payment_rows):
    rows = [r for r in payment_rows if r.get("player_id") == player_id]

    if not rows:
        return {
            "label": "Δεν έχει καταχωρηθεί πρώτη πληρωμή",
            "state": "none",
            "last_paid_on": None,
            "next_due": None,
            "last_covered_month": None,
        }

    last_paid_on = max(
        pd.to_datetime(r.get("paid_on")).date()
        for r in rows
        if r.get("paid_on")
    )

    covered = [
        r for r in rows
        if r.get("coverage_month")
    ]

    if not covered:
        return {
            "label": "Δεν έχει καταχωρηθεί πρώτη πληρωμή",
            "state": "none",
            "last_paid_on": last_paid_on,
            "next_due": None,
            "last_covered_month": None,
        }

    latest_row = max(
        covered,
        key=lambda r: pd.to_datetime(r.get("coverage_month")).date(),
    )

    latest_month = month_start(latest_row.get("coverage_month"))
    anchor_paid_on = pd.to_datetime(latest_row.get("paid_on")).date()
    next_month = latest_month + relativedelta(months=1)

    next_due = safe_date_with_day(
        next_month.year,
        next_month.month,
        anchor_paid_on.day,
    )

    if date.today() > next_due:
        state = "overdue"
        label = "🔴 ΕΚΠΡΟΘΕΣΜΟΣ"
    else:
        state = "ok"
        label = "🟢 ΕΝΤΑΞΕΙ"

    return {
        "label": label,
        "state": state,
        "last_paid_on": last_paid_on,
        "next_due": next_due,
        "last_covered_month": latest_month,
    }


def next_suggested_month(player_id, payment_rows):
    covered = [
        month_start(r["coverage_month"])
        for r in payment_rows
        if r.get("player_id") == player_id and r.get("coverage_month")
    ]

    if not covered:
        return date.today().replace(day=1)

    return max(covered) + relativedelta(months=1)


# ============================================================
# LOGIN
# ============================================================

require_login()
ensure_photo_bucket()

sb = get_user_client()
profile = st.session_state.profile


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(APP_NAME)
st.sidebar.caption(profile.get("full_name") or profile.get("email"))
st.sidebar.caption("Admin" if role_is_admin() else "Coach")

pages = [
    "🏠 Dashboard",
    "👥 Παίκτες",
    "✅ Παρουσίες",
]

if can_access_payments():
    pages.append("💳 Πληρωμές")

if role_is_admin():
    pages.append("⚙️ Χρήστες")

page = st.sidebar.radio("Μενού", pages)
st.sidebar.divider()

if st.sidebar.button("Αποσύνδεση", use_container_width=True):
    logout()

show_flash()


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":
    st.title("Dashboard")

    players = get_players()
    attendance = get_all_attendance()

    total_records = len(attendance)
    total_present = sum(1 for x in attendance if x.get("present") is True)

    attendance_pct = (
        round((total_present / total_records) * 100, 1)
        if total_records > 0
        else 0
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Ενεργοί παίκτες", len(players))
    c2.metric("Καταχωρήσεις παρουσιών", total_records)
    c3.metric("Συνολική παρουσία", f"{attendance_pct}%")

    st.subheader("Παίκτες")

    if players:
        rows = []
        for p in players:
            rows.append(
                {
                    "Νο": p.get("jersey_number") or "—",
                    "Ονοματεπώνυμο": p.get("full_name"),
                    "Ημερομηνία Γέννησης": format_date(p.get("birth_date")),
                    "Τμήμα": p.get("team") or "—",
                    "Active": bool(p.get("active", True)),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Δεν έχουν προστεθεί παίκτες ακόμη.")


# ============================================================
# ΠΑΙΚΤΕΣ
# ============================================================

elif page == "👥 Παίκτες":
    st.title("Παίκτες")

    tab_list, tab_new = st.tabs(
        [
            "Λίστα παικτών",
            "➕ Νέος παίκτης",
        ]
    )

    with tab_list:
        players = get_players(active_only=False)

        if not players:
            st.info("Δεν υπάρχουν παίκτες.")
        else:
            # Header
            header = st.columns([0.6, 0.7, 2.4, 1.6, 1.8, 1.2, 0.8, 1.2])
            header[0].markdown("**Φωτο**")
            header[1].markdown("**Νο**")
            header[2].markdown("**Ονοματεπώνυμο**")
            header[3].markdown("**Ημ. Γέννησης**")
            header[4].markdown("**Τμήμα**")
            header[5].markdown("**Μέγεθος**")
            header[6].markdown("**Active**")
            header[7].markdown("**Ενέργειες**")

            st.divider()

            for p in players:
                cols = st.columns([0.6, 0.7, 2.4, 1.6, 1.8, 1.2, 0.8, 1.2])

                with cols[0]:
                    show_player_photo(p, width=48)

                cols[1].write(p.get("jersey_number") or "—")
                cols[2].write(p.get("full_name") or "—")
                cols[3].write(format_date(p.get("birth_date")))
                cols[4].write(p.get("team") or "—")
                cols[5].write(p.get("jersey_size") or "—")
                cols[6].write("✅" if p.get("active", True) else "—")

                with cols[7]:
                    c_edit, c_delete = st.columns(2)

                    if c_edit.button(
                        "✏️",
                        key=f"player_edit_btn_{p['id']}",
                        help="Edit",
                        use_container_width=True,
                    ):
                        st.session_state["edit_player_id"] = p["id"]
                        st.session_state.pop("delete_player_id", None)

                    if c_delete.button(
                        "🗑️",
                        key=f"player_delete_btn_{p['id']}",
                        help="Διαγραφή",
                        use_container_width=True,
                    ):
                        st.session_state["delete_player_id"] = p["id"]
                        st.session_state.pop("edit_player_id", None)

                st.divider()

            # Inline edit panel
            edit_id = st.session_state.get("edit_player_id")
            if edit_id:
                selected = next((p for p in players if p["id"] == edit_id), None)

                if selected:
                    st.subheader(f"✏️ Edit — {selected.get('full_name')}")

                    current_birth = (
                        pd.to_datetime(selected.get("birth_date")).date()
                        if selected.get("birth_date")
                        else date(2012, 1, 1)
                    )

                    current_team = selected.get("team")
                    team_index = TEAMS.index(current_team) if current_team in TEAMS else 0

                    current_size = selected.get("jersey_size")
                    size_index = (
                        JERSEY_SIZES.index(current_size)
                        if current_size in JERSEY_SIZES
                        else 0
                    )

                    current_fee = float(selected.get("monthly_fee") or 0)

                    existing_photo = signed_photo_url(selected.get("photo_path"))
                    if existing_photo:
                        st.image(existing_photo, width=120)

                    with st.form(f"edit_player_form_{selected['id']}"):
                        edit_name = st.text_input(
                            "Ονοματεπώνυμο",
                            value=selected.get("full_name") or "",
                        )

                        edit_birth = st.date_input(
                            "Ημερομηνία Γέννησης",
                            value=current_birth,
                            min_value=date(1990, 1, 1),
                            max_value=date.today(),
                            format="DD/MM/YYYY",
                        )

                        edit_team = st.selectbox(
                            "Τμήμα",
                            TEAMS,
                            index=team_index,
                        )

                        edit_number = st.text_input(
                            "Νούμερο φανέλας",
                            value=selected.get("jersey_number") or "",
                        )

                        edit_size = st.selectbox(
                            "Μέγεθος φανέλας",
                            JERSEY_SIZES,
                            index=size_index,
                        )

                        edit_fee = st.number_input(
                            "Μηνιαίο ποσό (€)",
                            min_value=0.0,
                            value=current_fee,
                            step=5.0,
                        )

                        edit_photo = st.file_uploader(
                            "Νέα φωτογραφία (προαιρετικό)",
                            type=["jpg", "jpeg", "png", "webp"],
                            max_upload_size=5,
                            key=f"edit_photo_{selected['id']}",
                        )

                        remove_photo = st.checkbox(
                            "Αφαίρεση υπάρχουσας φωτογραφίας",
                            value=False,
                        )

                        edit_notes = st.text_area(
                            "Σημειώσεις",
                            value=selected.get("notes") or "",
                        )

                        edit_active = st.checkbox(
                            "Active",
                            value=bool(selected.get("active", True)),
                        )

                        save_edit = st.form_submit_button(
                            "Αποθήκευση αλλαγών",
                            use_container_width=True,
                        )

                    if save_edit:
                        if not edit_name.strip():
                            st.error("Το ονοματεπώνυμο είναι υποχρεωτικό.")
                        elif duplicate_player_exists(
                            edit_name,
                            edit_birth,
                            exclude_id=selected["id"],
                        ):
                            st.error(
                                "Υπάρχει ήδη παίκτης με το ίδιο όνομα και ημερομηνία γέννησης."
                            )
                        else:
                            photo_path = selected.get("photo_path")

                            try:
                                if remove_photo and photo_path:
                                    remove_player_photo(photo_path)
                                    photo_path = None

                                if edit_photo is not None:
                                    if photo_path:
                                        remove_player_photo(photo_path)
                                    photo_path = upload_player_photo(
                                        selected["id"],
                                        edit_photo,
                                    )
                            except Exception:
                                st.warning(
                                    "Οι πληροφορίες θα αποθηκευτούν, αλλά υπήρξε πρόβλημα με τη φωτογραφία."
                                )

                            (
                                sb.table("players")
                                .update(
                                    {
                                        "full_name": edit_name.strip(),
                                        "birth_date": str(edit_birth),
                                        "team": edit_team,
                                        "jersey_number": edit_number.strip() or None,
                                        "jersey_size": edit_size,
                                        "monthly_fee": float(edit_fee),
                                        "photo_path": photo_path,
                                        "notes": edit_notes.strip() or None,
                                        "active": bool(edit_active),
                                    }
                                )
                                .eq("id", selected["id"])
                                .execute()
                            )

                            st.session_state.pop("edit_player_id", None)
                            set_flash("✅ Οι αλλαγές του παίκτη αποθηκεύτηκαν.")
                            st.rerun()

            # Inline delete panel
            delete_id = st.session_state.get("delete_player_id")
            if delete_id:
                selected = next((p for p in players if p["id"] == delete_id), None)

                if selected:
                    st.subheader(f"🗑️ Διαγραφή — {selected.get('full_name')}")
                    st.warning(
                        "Η οριστική διαγραφή διαγράφει μαζί τις παρουσίες "
                        "και τις πληρωμές που συνδέονται με τον παίκτη."
                    )

                    confirm_delete = st.checkbox(
                        "Επιβεβαίωση διαγραφής",
                        key=f"confirm_player_delete_{selected['id']}",
                    )

                    if st.button(
                        "Οριστική διαγραφή",
                        type="primary",
                        disabled=not confirm_delete,
                        key=f"delete_player_final_{selected['id']}",
                    ):
                        remove_player_photo(selected.get("photo_path"))

                        (
                            sb.table("players")
                            .delete()
                            .eq("id", selected["id"])
                            .execute()
                        )

                        st.session_state.pop("delete_player_id", None)
                        set_flash("✅ Η διαγραφή ολοκληρώθηκε.")
                        st.rerun()

    with tab_new:
        with st.form("new_player"):
            full_name = st.text_input("Ονοματεπώνυμο *")

            birth_date = st.date_input(
                "Ημερομηνία Γέννησης",
                value=date(2012, 1, 1),
                min_value=date(1990, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
            )

            team = st.selectbox("Τμήμα", TEAMS)

            jersey_number = st.text_input(
                "Νούμερο φανέλας",
                placeholder="π.χ. 7, 23, 00",
            )

            jersey_size = st.selectbox(
                "Μέγεθος φανέλας",
                JERSEY_SIZES,
            )

            monthly_fee = st.number_input(
                "Μηνιαίο ποσό (€)",
                min_value=0.0,
                value=0.0,
                step=5.0,
            )

            photo = st.file_uploader(
                "Φωτογραφία παίκτη",
                type=["jpg", "jpeg", "png", "webp"],
                max_upload_size=5,
            )

            notes = st.text_area("Σημειώσεις")

            save = st.form_submit_button(
                "Αποθήκευση παίκτη",
                use_container_width=True,
            )

        if save:
            if not full_name.strip():
                st.error("Το ονοματεπώνυμο είναι υποχρεωτικό.")
            elif duplicate_player_exists(full_name, birth_date):
                st.error(
                    "Υπάρχει ήδη παίκτης με το ίδιο όνομα και ημερομηνία γέννησης."
                )
            else:
                response = (
                    sb.table("players")
                    .insert(
                        {
                            "full_name": full_name.strip(),
                            "birth_date": str(birth_date),
                            "team": team,
                            "jersey_number": jersey_number.strip() or None,
                            "jersey_size": jersey_size,
                            "monthly_fee": float(monthly_fee),
                            "notes": notes.strip() or None,
                            "active": True,
                            "created_by": st.session_state.user.id,
                        }
                    )
                    .execute()
                )

                new_player = response.data[0] if response.data else None

                if new_player and photo is not None:
                    try:
                        path = upload_player_photo(new_player["id"], photo)
                        (
                            sb.table("players")
                            .update({"photo_path": path})
                            .eq("id", new_player["id"])
                            .execute()
                        )
                    except Exception:
                        set_flash(
                            "✅ Ο παίκτης αποθηκεύτηκε, αλλά η φωτογραφία δεν ανέβηκε.",
                            "warning",
                        )
                        st.rerun()

                set_flash("✅ Ο παίκτης αποθηκεύτηκε.")
                st.rerun()


# ============================================================
# ΠΑΡΟΥΣΙΕΣ
# ============================================================

elif page == "✅ Παρουσίες":
    st.title("Παρουσίες")

    all_players = get_players()

    if not all_players:
        st.info("Πρόσθεσε πρώτα παίκτες.")
        st.stop()

    available_teams = [
        t for t in TEAMS
        if any((p.get("team") or "") == t for p in all_players)
    ]

    if not available_teams:
        st.info("Δεν υπάρχουν ενεργοί παίκτες σε τμήμα.")
        st.stop()

    # ΠΡΩΤΗ επιλογή: τμήμα
    selected_team = st.selectbox(
        "Τμήμα",
        available_teams,
        key="attendance_team",
    )

    team_players = [
        p for p in all_players
        if p.get("team") == selected_team
    ]

    # ΔΕΥΤΕΡΗ επιλογή: προαιρετικά συγκεκριμένος παίκτης, searchable.
    selected_player = searchable_player_select(
        "Παίκτης (προαιρετικά — γράψε όνομα για αναζήτηση)",
        team_players,
        key="attendance_player_filter",
        include_all=True,
    )

    view_players = (
        [selected_player]
        if selected_player is not None
        else team_players
    )

    attendance_rows = get_team_attendance(selected_team)

    tab_record, tab_day, tab_week, tab_month, tab_player = st.tabs(
        [
            "📝 Καταχώρηση",
            "📅 Ανά ημέρα",
            "🗓️ Ανά εβδομάδα",
            "📆 Ανά μήνα",
            "👤 Ιστορικό παίκτη",
        ]
    )

    # ---------------- Καταχώρηση ----------------
    with tab_record:
        st.subheader(f"Καταχώρηση — {selected_team}")

        training_date = st.date_input(
            "Ημερομηνία προπόνησης",
            value=date.today(),
            format="DD/MM/YYYY",
            key="attendance_record_date",
        )

        st.caption(f"{len(team_players)} παίκτες")

        with st.form("attendance_form"):
            presence = {}

            for p in team_players:
                row = st.columns([0.7, 4.3, 1.4])

                with row[0]:
                    show_player_photo(p, width=44)

                row[1].markdown(f"**{player_short_name(p)}**")

                with row[2]:
                    presence[p["id"]] = st.checkbox(
                        "Παρών",
                        value=True,
                        key=f"attendance_{training_date}_{p['id']}",
                    )

            submit_att = st.form_submit_button(
                "Αποθήκευση παρουσιών",
                use_container_width=True,
            )

        if submit_att:
            for p in team_players:
                existing = (
                    sb.table("attendance")
                    .select("id")
                    .eq("player_id", p["id"])
                    .eq("training_date", str(training_date))
                    .execute()
                    .data
                )

                payload = {
                    "player_id": p["id"],
                    "training_date": str(training_date),
                    "present": bool(presence[p["id"]]),
                    "recorded_by": st.session_state.user.id,
                }

                if existing:
                    (
                        sb.table("attendance")
                        .update(payload)
                        .eq("id", existing[0]["id"])
                        .execute()
                    )
                else:
                    sb.table("attendance").insert(payload).execute()

            set_flash(
                f"✅ Οι παρουσίες του {selected_team} για {training_date.strftime('%d/%m/%Y')} αποθηκεύτηκαν."
            )
            st.rerun()

    # ---------------- Ανά ημέρα ----------------
    with tab_day:
        day = st.date_input(
            "Ημερομηνία",
            value=date.today(),
            format="DD/MM/YYYY",
            key="attendance_day_view",
        )

        day_df, training_dates = attendance_matrix(
            view_players,
            attendance_rows,
            start_date=day,
            end_date=day,
        )

        if day_df.empty or not training_dates:
            st.info("Δεν υπάρχει καταχωρημένη προπόνηση για αυτή την ημερομηνία.")
        else:
            st.dataframe(day_df, use_container_width=True, hide_index=True)

            excel_data = excel_bytes_from_dataframe(
                day_df,
                sheet_name="Ημέρα",
                title=f"{selected_team} — {day.strftime('%d/%m/%Y')}",
            )

            st.download_button(
                "⬇️ Εξαγωγή σε Excel",
                data=excel_data,
                file_name=f"parousies_{selected_team}_{day.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ---------------- Ανά εβδομάδα ----------------
    with tab_week:
        focus_day = st.date_input(
            "Επίλεξε ημέρα της εβδομάδας",
            value=date.today(),
            format="DD/MM/YYYY",
            key="attendance_week_view",
        )

        monday = focus_day - timedelta(days=focus_day.weekday())
        sunday = monday + timedelta(days=6)

        st.caption(
            f"Εβδομάδα: {monday.strftime('%d/%m/%Y')} – {sunday.strftime('%d/%m/%Y')}"
        )

        week_df, week_dates = attendance_matrix(
            view_players,
            attendance_rows,
            start_date=monday,
            end_date=sunday,
        )

        if week_df.empty or not week_dates:
            st.info("Δεν υπάρχουν καταχωρημένες προπονήσεις αυτή την εβδομάδα.")
        else:
            st.dataframe(week_df, use_container_width=True, hide_index=True)

            excel_data = excel_bytes_from_dataframe(
                week_df,
                sheet_name="Εβδομάδα",
                title=(
                    f"{selected_team} — "
                    f"{monday.strftime('%d/%m/%Y')} έως {sunday.strftime('%d/%m/%Y')}"
                ),
            )

            st.download_button(
                "⬇️ Εξαγωγή σε Excel",
                data=excel_data,
                file_name=f"parousies_{selected_team}_week_{monday.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ---------------- Ανά μήνα ----------------
    with tab_month:
        month_pick = st.date_input(
            "Επίλεξε μήνα",
            value=date.today().replace(day=1),
            format="DD/MM/YYYY",
            key="attendance_month_view",
        )

        first_day = month_pick.replace(day=1)
        last_day = (
            first_day + relativedelta(months=1) - timedelta(days=1)
        )

        st.caption(
            f"{GREEK_MONTHS[first_day.month]} {first_day.year}"
        )

        month_df, month_dates = attendance_matrix(
            view_players,
            attendance_rows,
            start_date=first_day,
            end_date=last_day,
        )

        if month_df.empty or not month_dates:
            st.info("Δεν υπάρχουν καταχωρημένες προπονήσεις αυτόν τον μήνα.")
        else:
            st.dataframe(month_df, use_container_width=True, hide_index=True)

            excel_data = excel_bytes_from_dataframe(
                month_df,
                sheet_name="Μήνας",
                title=f"{selected_team} — {GREEK_MONTHS[first_day.month]} {first_day.year}",
            )

            st.download_button(
                "⬇️ Εξαγωγή σε Excel",
                data=excel_data,
                file_name=(
                    f"parousies_{selected_team}_{first_day.year}_{first_day.month:02d}.xlsx"
                ),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ---------------- Ιστορικό παίκτη ----------------
    with tab_player:
        history_player = searchable_player_select(
            "Παίκτης",
            team_players,
            key="attendance_history_player",
        )

        if history_player:
            head = st.columns([0.8, 4])
            with head[0]:
                show_player_photo(history_player, width=70)
            head[1].markdown(
                f"### {player_short_name(history_player)}\n"
                f"**Τμήμα:** {selected_team}"
            )

            rows = [
                r for r in attendance_rows
                if r.get("player_id") == history_player["id"]
            ]

            rows = sorted(
                rows,
                key=lambda r: pd.to_datetime(r.get("training_date")).date(),
                reverse=True,
            )

            if not rows:
                st.info("Δεν υπάρχουν καταχωρημένες παρουσίες για αυτόν τον παίκτη.")
            else:
                present_count = sum(1 for r in rows if r.get("present") is True)
                absent_count = sum(1 for r in rows if r.get("present") is False)
                total = present_count + absent_count
                pct = round((present_count / total) * 100, 1) if total else 0

                c1, c2, c3 = st.columns(3)
                c1.metric("Παρουσίες", present_count)
                c2.metric("Απουσίες", absent_count)
                c3.metric("Ποσοστό", f"{pct}%")

                history_df = pd.DataFrame(
                    [
                        {
                            "Ημερομηνία": format_date(r.get("training_date")),
                            "Κατάσταση": "✅ Παρών" if r.get("present") else "❌ Απών",
                            "Καταχώρηση από": (r.get("profiles") or {}).get("full_name") or "—",
                        }
                        for r in rows
                    ]
                )

                st.dataframe(
                    history_df,
                    use_container_width=True,
                    hide_index=True,
                )

                excel_data = excel_bytes_from_dataframe(
                    history_df,
                    sheet_name="Ιστορικό",
                    title=f"{player_short_name(history_player)} — {selected_team}",
                )

                st.download_button(
                    "⬇️ Εξαγωγή ιστορικού σε Excel",
                    data=excel_data,
                    file_name=f"parousies_{history_player['full_name']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


# ============================================================
# ΠΛΗΡΩΜΕΣ
# ============================================================

elif page == "💳 Πληρωμές":
    if not can_access_payments():
        st.error("Δεν έχεις πρόσβαση στις Πληρωμές.")
        st.stop()

    st.title("Πληρωμές")

    players = get_players()

    if not players:
        st.info("Δεν υπάρχουν ενεργοί παίκτες.")
        st.stop()

    payment_rows = get_all_payments()

    payment_teams = [
        t for t in TEAMS
        if any(p.get("team") == t for p in players)
    ]

    tab_status, tab_record, tab_history = st.tabs(
        [
            "Κατάσταση",
            "➕ Καταχώρηση πληρωμής",
            "Ιστορικό",
        ]
    )

    # ---------------- Κατάσταση ----------------
    with tab_status:
        selected_team = st.selectbox(
            "Τμήμα",
            payment_teams,
            key="payments_status_team",
        )

        team_players = [
            p for p in players
            if p.get("team") == selected_team
        ]

        status_player = searchable_player_select(
            "Παίκτης (προαιρετικά — αναζήτηση)",
            team_players,
            key="payments_status_player",
            include_all=True,
        )

        displayed_players = (
            [status_player] if status_player else team_players
        )

        header = st.columns([0.55, 0.6, 2.2, 1.2, 1.5, 1.5, 1.7, 1.2])
        header[0].markdown("**Φωτο**")
        header[1].markdown("**Νο**")
        header[2].markdown("**Ονοματεπώνυμο**")
        header[3].markdown("**Ποσό**")
        header[4].markdown("**Τελ. πληρωμή**")
        header[5].markdown("**Επόμενη**")
        header[6].markdown("**Κατάσταση**")
        header[7].markdown("**Ενέργειες**")
        st.divider()

        for p in displayed_players:
            status = player_payment_status(p["id"], payment_rows)
            cols = st.columns([0.55, 0.6, 2.2, 1.2, 1.5, 1.5, 1.7, 1.2])

            with cols[0]:
                show_player_photo(p, width=44)

            cols[1].write(p.get("jersey_number") or "—")
            cols[2].write(p.get("full_name"))
            cols[3].write(format_money(p.get("monthly_fee")))
            cols[4].write(format_date(status.get("last_paid_on")))
            cols[5].write(format_date(status.get("next_due")) if status.get("next_due") else "—")

            if status["state"] == "overdue":
                cols[6].error("ΕΚΠΡΟΘΕΣΜΟΣ")
            elif status["state"] == "ok":
                cols[6].success("ΕΝΤΑΞΕΙ")
            else:
                cols[6].info("Δεν έχει καταχωρηθεί πρώτη πληρωμή")

            with cols[7]:
                e1, e2 = st.columns(2)

                if e1.button(
                    "✏️",
                    key=f"pay_manage_edit_{p['id']}",
                    help="Edit πληρωμής",
                    use_container_width=True,
                ):
                    st.session_state["payment_manage_player_id"] = p["id"]
                    st.session_state["payment_manage_mode"] = "edit"

                if e2.button(
                    "🗑️",
                    key=f"pay_manage_delete_{p['id']}",
                    help="Διαγραφή πληρωμής",
                    use_container_width=True,
                ):
                    st.session_state["payment_manage_player_id"] = p["id"]
                    st.session_state["payment_manage_mode"] = "delete"

            st.divider()

        manage_pid = st.session_state.get("payment_manage_player_id")
        manage_mode = st.session_state.get("payment_manage_mode")

        managed_player = next(
            (p for p in players if p["id"] == manage_pid),
            None,
        )

        if managed_player:
            player_rows = [
                r for r in payment_rows
                if r.get("player_id") == managed_player["id"]
            ]

            if not player_rows:
                st.info(
                    f"Δεν υπάρχουν πληρωμές για {player_short_name(managed_player)}."
                )
            else:
                player_rows = sorted(
                    player_rows,
                    key=lambda r: (
                        pd.to_datetime(r.get("paid_on")).date(),
                        pd.to_datetime(r.get("coverage_month")).date()
                        if r.get("coverage_month")
                        else date.min,
                    ),
                    reverse=True,
                )

                options = {
                    (
                        f"{format_date(r.get('paid_on'))} · "
                        f"{month_label(r.get('coverage_month')) if r.get('coverage_month') else 'Χωρίς μήνα'} · "
                        f"{format_money(r.get('amount'))}"
                    ): r
                    for r in player_rows
                }

                selected_label = st.selectbox(
                    "Επίλεξε πληρωμή",
                    list(options.keys()),
                    key=f"manage_payment_select_{managed_player['id']}",
                )

                selected_payment = options[selected_label]

                if manage_mode == "edit":
                    st.subheader(
                        f"✏️ Edit πληρωμής — {player_short_name(managed_player)}"
                    )

                    month_opts = month_options(
                        selected_payment.get("coverage_month") or date.today()
                    )
                    current_month = (
                        month_start(selected_payment.get("coverage_month"))
                        if selected_payment.get("coverage_month")
                        else date.today().replace(day=1)
                    )
                    month_index = (
                        month_opts.index(current_month)
                        if current_month in month_opts
                        else 24
                    )

                    with st.form(f"edit_payment_{selected_payment['id']}"):
                        edit_paid_on = st.date_input(
                            "Ημερομηνία πληρωμής",
                            value=pd.to_datetime(selected_payment.get("paid_on")).date(),
                            format="DD/MM/YYYY",
                        )

                        edit_month = st.selectbox(
                            "Μήνας που καλύπτει",
                            month_opts,
                            index=month_index,
                            format_func=month_label,
                            filter_mode="contains",
                        )

                        edit_amount = st.number_input(
                            "Ποσό (€)",
                            min_value=0.01,
                            value=float(selected_payment.get("amount") or 0),
                            step=5.0,
                        )

                        edit_note = st.text_area(
                            "Σημείωση",
                            value=selected_payment.get("note") or "",
                        )

                        save_payment_edit = st.form_submit_button(
                            "Αποθήκευση αλλαγών",
                            use_container_width=True,
                        )

                    if save_payment_edit:
                        duplicate_month = (
                            sb.table("payments")
                            .select("id")
                            .eq("player_id", managed_player["id"])
                            .eq("coverage_month", str(edit_month))
                            .neq("id", selected_payment["id"])
                            .execute()
                            .data
                        )

                        if duplicate_month:
                            st.error(
                                f"Υπάρχει ήδη καταχώρηση για {month_label(edit_month)}."
                            )
                        else:
                            (
                                sb.table("payments")
                                .update(
                                    {
                                        "paid_on": str(edit_paid_on),
                                        "coverage_month": str(edit_month),
                                        "amount": float(edit_amount),
                                        "note": edit_note.strip() or None,
                                    }
                                )
                                .eq("id", selected_payment["id"])
                                .execute()
                            )

                            st.session_state.pop("payment_manage_player_id", None)
                            st.session_state.pop("payment_manage_mode", None)
                            set_flash("✅ Η πληρωμή ενημερώθηκε.")
                            st.rerun()

                elif manage_mode == "delete":
                    st.subheader(
                        f"🗑️ Διαγραφή πληρωμής — {player_short_name(managed_player)}"
                    )

                    st.write(
                        f"**{format_date(selected_payment.get('paid_on'))} — "
                        f"{month_label(selected_payment.get('coverage_month')) if selected_payment.get('coverage_month') else 'Χωρίς μήνα'} — "
                        f"{format_money(selected_payment.get('amount'))}**"
                    )

                    confirm = st.checkbox(
                        "Επιβεβαίωση διαγραφής",
                        key=f"confirm_payment_delete_{selected_payment['id']}",
                    )

                    if st.button(
                        "Οριστική διαγραφή",
                        type="primary",
                        disabled=not confirm,
                        key=f"payment_delete_final_{selected_payment['id']}",
                    ):
                        (
                            sb.table("payments")
                            .delete()
                            .eq("id", selected_payment["id"])
                            .execute()
                        )

                        st.session_state.pop("payment_manage_player_id", None)
                        st.session_state.pop("payment_manage_mode", None)
                        set_flash("✅ Η διαγραφή ολοκληρώθηκε.")
                        st.rerun()

    # ---------------- Καταχώρηση πληρωμής ----------------
    with tab_record:
        payment_team = st.selectbox(
            "Τμήμα",
            payment_teams,
            key="payment_record_team",
        )

        team_players = [
            p for p in players
            if p.get("team") == payment_team
        ]

        payment_player = searchable_player_select(
            "Παίκτης — γράψε όνομα για αναζήτηση",
            team_players,
            key="payment_record_player",
        )

        if payment_player:
            info = st.columns([0.8, 3.2, 2])

            with info[0]:
                show_player_photo(payment_player, width=70)

            info[1].markdown(
                f"### {player_short_name(payment_player)}\n"
                f"**Τμήμα:** {payment_player.get('team')}"
            )
            info[2].metric(
                "Μηνιαίο ποσό",
                format_money(payment_player.get("monthly_fee")),
            )

            fee = float(payment_player.get("monthly_fee") or 0)

            if fee <= 0:
                st.warning(
                    "Δεν έχει οριστεί μηνιαίο ποσό για αυτόν τον παίκτη. "
                    "Πήγαινε Παίκτες → ✏️ Edit και συμπλήρωσέ το."
                )
            else:
                paid_on = st.date_input(
                    "Ημερομηνία πληρωμής",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    key="new_payment_date",
                )

                # Reset δυναμικών μηνών όταν αλλάζει παίκτης.
                if st.session_state.get("_payment_month_player") != payment_player["id"]:
                    st.session_state["_payment_month_player"] = payment_player["id"]
                    st.session_state["_payment_month_count"] = 1

                    # Καθαρίζουμε παλιές επιλογές.
                    for key in list(st.session_state.keys()):
                        if key.startswith("pay_month_choice_"):
                            st.session_state.pop(key, None)

                next_month = next_suggested_month(
                    payment_player["id"],
                    payment_rows,
                )

                c_add, c_remove = st.columns(2)

                if c_add.button(
                    "➕ Προσθήκη επιπλέον μήνα",
                    use_container_width=True,
                    key="add_payment_month",
                ):
                    st.session_state["_payment_month_count"] += 1
                    st.rerun()

                if c_remove.button(
                    "➖ Αφαίρεση τελευταίου μήνα",
                    use_container_width=True,
                    disabled=st.session_state["_payment_month_count"] <= 1,
                    key="remove_payment_month",
                ):
                    st.session_state["_payment_month_count"] = max(
                        1,
                        st.session_state["_payment_month_count"] - 1,
                    )
                    st.rerun()

                month_count = st.session_state["_payment_month_count"]
                opts = month_options(next_month)

                selected_months = []

                for i in range(month_count):
                    default_month = next_month + relativedelta(months=i)
                    default_index = (
                        opts.index(default_month)
                        if default_month in opts
                        else 24
                    )

                    chosen = st.selectbox(
                        f"Μήνας {i + 1}",
                        opts,
                        index=default_index,
                        format_func=month_label,
                        filter_mode="contains",
                        key=f"pay_month_choice_{payment_player['id']}_{i}",
                    )
                    selected_months.append(chosen)

                total_amount = fee * len(selected_months)

                st.metric(
                    "Συνολικό ποσό",
                    format_money(total_amount),
                )

                note = st.text_area(
                    "Σημείωση",
                    placeholder="Προαιρετικό",
                    key="new_payment_note",
                )

                if st.button(
                    "Καταχώρηση πληρωμής",
                    type="primary",
                    use_container_width=True,
                    key="save_multi_payment",
                ):
                    if len(set(selected_months)) != len(selected_months):
                        st.error("Έχεις επιλέξει τον ίδιο μήνα περισσότερες από μία φορές.")
                    else:
                        duplicates = []

                        for m in selected_months:
                            existing = (
                                sb.table("payments")
                                .select("id")
                                .eq("player_id", payment_player["id"])
                                .eq("coverage_month", str(m))
                                .execute()
                                .data
                            )

                            if existing:
                                duplicates.append(month_label(m))

                        if duplicates:
                            st.error(
                                "Υπάρχει ήδη πληρωμή για: "
                                + ", ".join(duplicates)
                            )
                        else:
                            batch_id = str(uuid.uuid4())

                            payload = [
                                {
                                    "player_id": payment_player["id"],
                                    "amount": fee,
                                    "paid_on": str(paid_on),
                                    "coverage_month": str(m),
                                    "payment_batch_id": batch_id,
                                    "note": note.strip() or None,
                                    "recorded_by": st.session_state.user.id,
                                }
                                for m in selected_months
                            ]

                            sb.table("payments").insert(payload).execute()

                            st.session_state["_payment_month_count"] = 1
                            set_flash(
                                "✅ Η πληρωμή καταχωρήθηκε: "
                                f"{format_money(total_amount)} για "
                                + ", ".join(month_label(m) for m in selected_months)
                                + "."
                            )
                            st.rerun()

    # ---------------- Ιστορικό ----------------
    with tab_history:
        history_team = st.selectbox(
            "Τμήμα",
            payment_teams,
            key="payment_history_team",
        )

        history_players = [
            p for p in players
            if p.get("team") == history_team
        ]

        history_player = searchable_player_select(
            "Παίκτης — αναζήτηση",
            history_players,
            key="payment_history_player",
        )

        if history_player:
            hcols = st.columns([0.8, 4])
            with hcols[0]:
                show_player_photo(history_player, width=70)
            hcols[1].markdown(
                f"### {player_short_name(history_player)}\n"
                f"**Μηνιαίο ποσό:** {format_money(history_player.get('monthly_fee'))}"
            )

            rows = [
                r for r in payment_rows
                if r.get("player_id") == history_player["id"]
            ]

            if not rows:
                st.info("Δεν έχει καταχωρηθεί πρώτη πληρωμή για αυτόν τον παίκτη.")
            else:
                # Σύνοψη ανά συναλλαγή/batch.
                batches = {}

                for r in rows:
                    batch = r.get("payment_batch_id") or r.get("id")
                    batches.setdefault(
                        batch,
                        {
                            "paid_on": r.get("paid_on"),
                            "total": 0.0,
                            "months": [],
                        },
                    )
                    batches[batch]["total"] += float(r.get("amount") or 0)

                    if r.get("coverage_month"):
                        batches[batch]["months"].append(
                            month_start(r.get("coverage_month"))
                        )

                st.subheader("Συναλλαγές")

                batch_rows = []
                for batch_id, data in sorted(
                    batches.items(),
                    key=lambda item: pd.to_datetime(item[1]["paid_on"]).date(),
                    reverse=True,
                ):
                    months = sorted(set(data["months"]))
                    batch_rows.append(
                        {
                            "Ημερομηνία πληρωμής": format_date(data["paid_on"]),
                            "Συνολικό ποσό": format_money(data["total"]),
                            "Μήνες": ", ".join(month_label(m) for m in months),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(batch_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                st.subheader("Αναλυτικές εγγραφές ανά μήνα")

                rows = sorted(
                    rows,
                    key=lambda r: (
                        pd.to_datetime(r.get("paid_on")).date(),
                        pd.to_datetime(r.get("coverage_month")).date()
                        if r.get("coverage_month")
                        else date.min,
                    ),
                    reverse=True,
                )

                for r in rows:
                    line = st.columns([1.4, 2.0, 1.2, 2.0, 1.0])

                    line[0].write(format_date(r.get("paid_on")))
                    line[1].write(
                        month_label(r.get("coverage_month"))
                        if r.get("coverage_month")
                        else "—"
                    )
                    line[2].write(format_money(r.get("amount")))
                    line[3].write(r.get("note") or "—")

                    with line[4]:
                        e1, e2 = st.columns(2)

                        if e1.button(
                            "✏️",
                            key=f"history_edit_payment_{r['id']}",
                            help="Edit",
                        ):
                            st.session_state["payment_manage_player_id"] = history_player["id"]
                            st.session_state["payment_manage_mode"] = "edit"
                            st.rerun()

                        if e2.button(
                            "🗑️",
                            key=f"history_delete_payment_{r['id']}",
                            help="Διαγραφή",
                        ):
                            st.session_state["payment_manage_player_id"] = history_player["id"]
                            st.session_state["payment_manage_mode"] = "delete"
                            st.rerun()

                    st.divider()


# ============================================================
# ΧΡΗΣΤΕΣ - ADMIN
# ============================================================

elif page == "⚙️ Χρήστες":
    if not role_is_admin():
        st.error("Δεν έχεις πρόσβαση.")
        st.stop()

    st.title("Διαχείριση χρηστών")

    admin = admin_client()

    profiles = (
        admin.table("profiles")
        .select(
            "id,email,full_name,role,active,"
            "can_view_payments,created_at"
        )
        .order("created_at")
        .execute()
        .data
        or []
    )

    st.caption(f"Εγκεκριμένοι λογαριασμοί: {len(profiles)} / 10")

    if profiles:
        display_rows = []

        for p in profiles:
            display_rows.append(
                {
                    "Ονοματεπώνυμο": p.get("full_name"),
                    "Email": p.get("email"),
                    "Ρόλος": p.get("role"),
                    "Ενεργός": bool(p.get("active", True)),
                    "Πληρωμές": (
                        "✅"
                        if (
                            p.get("role") == "admin"
                            or p.get("can_view_payments")
                        )
                        else "—"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(display_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("➕ Δημιουργία προπονητή")

    with st.form("create_coach"):
        coach_name = st.text_input("Ονοματεπώνυμο")
        coach_email = st.text_input("Email")
        coach_password = st.text_input(
            "Προσωρινός κωδικός",
            type="password",
        )
        coach_role = st.selectbox(
            "Ρόλος",
            ["coach", "admin"],
        )
        payment_access = st.checkbox(
            "Να έχει πρόσβαση στις Πληρωμές",
            value=False,
        )

        create = st.form_submit_button(
            "Δημιουργία χρήστη",
            use_container_width=True,
        )

    if create:
        if len(profiles) >= 10:
            st.error("Έχει συμπληρωθεί το όριο των 10 λογαριασμών.")

        elif (
            not coach_name.strip()
            or not coach_email.strip()
            or len(coach_password) < 8
        ):
            st.error(
                "Συμπλήρωσε όνομα, email και κωδικό "
                "τουλάχιστον 8 χαρακτήρων."
            )

        else:
            try:
                response = admin.auth.admin.create_user(
                    {
                        "email": coach_email.strip().lower(),
                        "password": coach_password,
                        "email_confirm": True,
                        "user_metadata": {
                            "full_name": coach_name.strip()
                        },
                    }
                )

                admin.table("profiles").insert(
                    {
                        "id": response.user.id,
                        "email": coach_email.strip().lower(),
                        "full_name": coach_name.strip(),
                        "role": coach_role,
                        "active": True,
                        "can_view_payments": bool(payment_access),
                    }
                ).execute()

                set_flash("✅ Ο χρήστης δημιουργήθηκε.")
                st.rerun()

            except Exception as e:
                st.error(f"Δεν δημιουργήθηκε ο χρήστης: {e}")

    st.subheader("Δικαιώματα χρήστη")

    selectable = {
        f'{p["full_name"]} — {p["email"]}': p
        for p in profiles
        if p["id"] != st.session_state.user.id
    }

    if selectable:
        selected_user_label = st.selectbox(
            "Χρήστης",
            list(selectable.keys()),
        )

        selected_user = selectable[selected_user_label]

        new_active = st.toggle(
            "Ενεργός λογαριασμός",
            value=bool(selected_user.get("active", True)),
            key=f"active_{selected_user['id']}",
        )

        new_payment_access = st.toggle(
            "Πρόσβαση στις Πληρωμές",
            value=bool(
                selected_user.get("can_view_payments", False)
            ),
            key=f"payaccess_{selected_user['id']}",
            disabled=selected_user.get("role") == "admin",
        )

        if st.button(
            "Αποθήκευση δικαιωμάτων",
            use_container_width=True,
        ):
            payload = {
                "active": new_active,
                "can_view_payments": (
                    True
                    if selected_user.get("role") == "admin"
                    else new_payment_access
                ),
            }

            (
                admin.table("profiles")
                .update(payload)
                .eq("id", selected_user["id"])
                .execute()
            )

            set_flash("✅ Τα δικαιώματα ενημερώθηκαν.")
            st.rerun()


st.caption(APP_NAME)
