import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from supabase import create_client

APP_NAME = "Ταυροι Καλαμαριας Coaches 🏀"

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
    "XS", "S", "M", "L", "XL", "XXL"
]

st.set_page_config(
    page_title="Ταυροι Καλαμαριας Coaches",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

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


def get_players(active_only=True):
    sb = get_user_client()
    query = sb.table("players").select("*").order("full_name")

    if active_only:
        query = query.eq("active", True)

    return query.execute().data or []


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


def player_display_name(player):
    number = (player.get("jersey_number") or "").strip()
    prefix = f"#{number} · " if number else ""
    return f'{prefix}{player.get("full_name")} — {player.get("team") or "Χωρίς τμήμα"}'


def player_short_name(player):
    number = (player.get("jersey_number") or "").strip()
    return f'#{number} {player.get("full_name")}' if number else player.get("full_name")


def payment_status(last_paid_on):
    if not last_paid_on:
        return {
            "label": "Δεν έχει καταχωρηθεί πρώτη πληρωμή",
            "next_due": None,
            "state": "none",
        }

    paid = pd.to_datetime(last_paid_on).date()
    next_due = paid + relativedelta(months=1)

    if date.today() > next_due:
        return {
            "label": "🔴 ΕΚΠΡΟΘΕΣΜΟΣ",
            "next_due": next_due,
            "state": "overdue",
        }

    return {
        "label": "🟢 ΕΝΤΑΞΕΙ",
        "next_due": next_due,
        "state": "ok",
    }


# ============================================================
# LOGIN
# ============================================================

require_login()
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


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":
    st.title("Dashboard")

    players = get_players()

    attendance = (
        sb.table("attendance")
        .select("id,present,training_date")
        .execute()
        .data
        or []
    )

    total_records = len(attendance)
    total_present = sum(
        1 for x in attendance if x.get("present") is True
    )

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
                    "Ημερομηνία Γέννησης": format_date(
                        p.get("birth_date")
                    ),
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

    tab_list, tab_new, tab_edit = st.tabs(
        [
            "Λίστα παικτών",
            "➕ Νέος παίκτης",
            "✏️ Edit / Διαγραφή",
        ]
    )

    with tab_list:
        players = get_players(active_only=False)

        if players:
            rows = []

            for p in players:
                rows.append(
                    {
                        "Νο": p.get("jersey_number") or "—",
                        "Ονοματεπώνυμο": p.get("full_name"),
                        "Ημερομηνία Γέννησης": format_date(
                            p.get("birth_date")
                        ),
                        "Τμήμα": p.get("team") or "—",
                        "Μέγεθος Φανέλας": p.get("jersey_size") or "—",
                        "Active": bool(p.get("active", True)),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Δεν υπάρχουν παίκτες.")

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

            team = st.selectbox(
                "Τμήμα",
                TEAMS,
            )

            jersey_number = st.text_input(
                "Νούμερο φανέλας",
                placeholder="π.χ. 7, 23, 00",
            )

            jersey_size = st.selectbox(
                "Μέγεθος φανέλας",
                JERSEY_SIZES,
            )

            notes = st.text_area("Σημειώσεις")

            save = st.form_submit_button(
                "Αποθήκευση παίκτη",
                use_container_width=True,
            )

        if save:
            if not full_name.strip():
                st.error("Το ονοματεπώνυμο είναι υποχρεωτικό.")
            else:
                sb.table("players").insert(
                    {
                        "full_name": full_name.strip(),
                        "birth_date": str(birth_date),
                        "team": team,
                        "jersey_number": jersey_number.strip() or None,
                        "jersey_size": jersey_size,
                        "notes": notes.strip() or None,
                        "active": True,
                        "created_by": st.session_state.user.id,
                    }
                ).execute()

                st.success("Ο παίκτης προστέθηκε.")
                st.rerun()

    with tab_edit:
        players = get_players(active_only=False)

        if not players:
            st.info("Δεν υπάρχουν παίκτες.")
        else:
            label_to_player = {
                player_display_name(p): p
                for p in players
            }

            selected_label = st.selectbox(
                "Επίλεξε παίκτη",
                list(label_to_player.keys()),
                key="edit_player_select",
            )

            selected = label_to_player[selected_label]

            current_birth = (
                pd.to_datetime(selected.get("birth_date")).date()
                if selected.get("birth_date")
                else date(2012, 1, 1)
            )

            current_team = selected.get("team")
            team_index = (
                TEAMS.index(current_team)
                if current_team in TEAMS
                else 0
            )

            current_size = selected.get("jersey_size")
            size_index = (
                JERSEY_SIZES.index(current_size)
                if current_size in JERSEY_SIZES
                else 0
            )

            with st.form("edit_player_form"):
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
                    key="edit_team",
                )

                edit_number = st.text_input(
                    "Νούμερο φανέλας",
                    value=selected.get("jersey_number") or "",
                )

                edit_size = st.selectbox(
                    "Μέγεθος φανέλας",
                    JERSEY_SIZES,
                    index=size_index,
                    key="edit_size",
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
                else:
                    (
                        sb.table("players")
                        .update(
                            {
                                "full_name": edit_name.strip(),
                                "birth_date": str(edit_birth),
                                "team": edit_team,
                                "jersey_number": edit_number.strip() or None,
                                "jersey_size": edit_size,
                                "notes": edit_notes.strip() or None,
                                "active": bool(edit_active),
                            }
                        )
                        .eq("id", selected["id"])
                        .execute()
                    )

                    st.success("Οι αλλαγές αποθηκεύτηκαν.")
                    st.rerun()

            st.divider()
            st.subheader("Οριστική διαγραφή παίκτη")

            st.warning(
                "Η οριστική διαγραφή παίκτη διαγράφει μαζί και "
                "τις παρουσίες και τις πληρωμές που συνδέονται με αυτόν."
            )

            confirm_delete = st.checkbox(
                "Επιβεβαίωση διαγραφής",
                key=f"confirm_player_delete_{selected['id']}",
            )

            if st.button(
                "Διαγραφή παίκτη",
                type="primary",
                disabled=not confirm_delete,
                use_container_width=True,
            ):
                (
                    sb.table("players")
                    .delete()
                    .eq("id", selected["id"])
                    .execute()
                )

                st.success("Ο παίκτης διαγράφηκε οριστικά.")
                st.rerun()


# ============================================================
# ΠΑΡΟΥΣΙΕΣ
# ============================================================

elif page == "✅ Παρουσίες":
    st.title("Παρουσίες")

    players = get_players()

    if not players:
        st.info("Πρόσθεσε πρώτα παίκτες.")

    else:
        player_teams = sorted(
            {
                p.get("team") or "Χωρίς τμήμα"
                for p in players
            }
        )

        teams = [
            t for t in TEAMS if t in player_teams
        ] + [
            t for t in player_teams if t not in TEAMS
        ]

        selected_team = st.selectbox(
            "Τμήμα",
            teams,
        )

        training_date = st.date_input(
            "Ημερομηνία προπόνησης",
            value=date.today(),
            format="DD/MM/YYYY",
        )

        team_players = [
            p
            for p in players
            if (p.get("team") or "Χωρίς τμήμα") == selected_team
        ]

        st.caption(
            f"{len(team_players)} παίκτες στο τμήμα {selected_team}"
        )

        with st.form("attendance_form"):
            st.write("Τσέκαρε όσους ήταν **παρόντες**.")

            presence = {}

            for p in team_players:
                presence[p["id"]] = st.checkbox(
                    player_short_name(p),
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

            st.success("Οι παρουσίες αποθηκεύτηκαν.")

        st.divider()
        st.subheader("Ιστορικό παρουσιών")

        history_team = st.selectbox(
            "Προβολή ιστορικού για τμήμα",
            teams,
            key="history_team",
        )

        att = (
            sb.table("attendance")
            .select(
                "training_date,present,"
                "players(full_name,team,jersey_number),"
                "profiles(full_name)"
            )
            .order("training_date", desc=True)
            .limit(500)
            .execute()
            .data
            or []
        )

        rows = []

        for r in att:
            player_data = r.get("players") or {}
            recorder_data = r.get("profiles") or {}

            if (
                player_data.get("team") or "Χωρίς τμήμα"
            ) != history_team:
                continue

            rows.append(
                {
                    "Ημερομηνία": format_date(
                        r.get("training_date")
                    ),
                    "Νο": player_data.get("jersey_number") or "—",
                    "Παίκτης": player_data.get("full_name"),
                    "Παρουσία": (
                        "✅ Παρών"
                        if r.get("present")
                        else "❌ Απών"
                    ),
                    "Καταχώρηση από": recorder_data.get("full_name"),
                }
            )

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Δεν υπάρχουν ακόμη καταχωρήσεις παρουσιών "
                "για αυτό το τμήμα."
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

    player_by_id = {p["id"]: p for p in players}
    label_to_id = {
        player_display_name(p): p["id"]
        for p in players
    }

    settings_rows = (
        sb.table("player_payment_settings")
        .select("player_id,monthly_amount")
        .execute()
        .data
        or []
    )

    monthly_amount_by_player = {
        r["player_id"]: r.get("monthly_amount")
        for r in settings_rows
    }

    payment_rows = (
        sb.table("payments")
        .select(
            "id,player_id,amount,paid_on,note,created_at,"
            "profiles(full_name)"
        )
        .order("paid_on", desc=True)
        .execute()
        .data
        or []
    )

    latest_by_player = {}

    for r in payment_rows:
        pid = r.get("player_id")

        if pid and pid not in latest_by_player:
            latest_by_player[pid] = r

    tab_status, tab_record, tab_amount, tab_history, tab_edit = st.tabs(
        [
            "Κατάσταση",
            "➕ Καταχώρηση πληρωμής",
            "💶 Ποσό παίκτη",
            "Ιστορικό",
            "✏️ Edit / Διαγραφή",
        ]
    )

    with tab_status:
        st.subheader("Κατάσταση πληρωμών")

        status_rows = []

        for p in players:
            pid = p["id"]
            latest = latest_by_player.get(pid)
            last_paid_on = latest.get("paid_on") if latest else None
            status = payment_status(last_paid_on)

            status_rows.append(
                {
                    "Νο": p.get("jersey_number") or "—",
                    "Ονοματεπώνυμο": p.get("full_name"),
                    "Τμήμα": p.get("team") or "—",
                    "Ποσό": format_money(
                        monthly_amount_by_player.get(pid)
                    ),
                    "Τελευταία πληρωμή": (
                        format_date(last_paid_on)
                        if last_paid_on
                        else "—"
                    ),
                    "Επόμενη πληρωμή": (
                        status["next_due"].strftime("%d/%m/%Y")
                        if status["next_due"]
                        else "—"
                    ),
                    "Κατάσταση": status["label"],
                    "_state": status["state"],
                }
            )

        status_df = pd.DataFrame(status_rows)

        def row_style(row):
            state = row.get("_state")

            if state == "overdue":
                return [
                    "background-color: #ffd6d6; color: #8a0000;"
                ] * len(row)

            if state == "ok":
                return [
                    "background-color: #e7f6ea;"
                ] * len(row)

            return [""] * len(row)

        visible_cols = [
            "Νο",
            "Ονοματεπώνυμο",
            "Τμήμα",
            "Ποσό",
            "Τελευταία πληρωμή",
            "Επόμενη πληρωμή",
            "Κατάσταση",
        ]

        styled = (
            status_df[visible_cols + ["_state"]]
            .style
            .apply(row_style, axis=1)
            .hide(axis="columns", subset=["_state"])
        )

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Ο υπολογισμός του μήνα ξεκινά από την ημερομηνία "
            "της τελευταίας καταχωρημένης πληρωμής."
        )

    with tab_record:
        st.subheader("Νέα πληρωμή")

        selected_label = st.selectbox(
            "Παίκτης",
            list(label_to_id.keys()),
            key="payment_player",
        )

        selected_pid = label_to_id[selected_label]
        saved_amount = monthly_amount_by_player.get(selected_pid)

        default_amount = (
            float(saved_amount)
            if saved_amount is not None
            else 0.0
        )

        with st.form("new_payment_form"):
            amount = st.number_input(
                "Ποσό (€)",
                min_value=0.0,
                value=default_amount,
                step=5.0,
            )

            paid_on = st.date_input(
                "Ημερομηνία πληρωμής",
                value=date.today(),
                format="DD/MM/YYYY",
            )

            note = st.text_area(
                "Σημείωση",
                placeholder="Προαιρετικό",
            )

            submit_payment = st.form_submit_button(
                "Καταχώρηση πληρωμής",
                use_container_width=True,
            )

        if submit_payment:
            if amount <= 0:
                st.error("Το ποσό πρέπει να είναι μεγαλύτερο από 0.")
            else:
                sb.table("payments").insert(
                    {
                        "player_id": selected_pid,
                        "amount": float(amount),
                        "paid_on": str(paid_on),
                        "note": note.strip() or None,
                        "recorded_by": st.session_state.user.id,
                    }
                ).execute()

                st.success("Η πληρωμή καταχωρήθηκε.")
                st.rerun()

    with tab_amount:
        st.subheader("Μηνιαίο ποσό παίκτη")

        amount_player_label = st.selectbox(
            "Παίκτης",
            list(label_to_id.keys()),
            key="amount_player",
        )

        amount_pid = label_to_id[amount_player_label]
        existing_amount = monthly_amount_by_player.get(amount_pid)

        with st.form("monthly_amount_form"):
            monthly_amount = st.number_input(
                "Μηνιαίο ποσό (€)",
                min_value=0.0,
                value=float(existing_amount or 0.0),
                step=5.0,
            )

            save_amount = st.form_submit_button(
                "Αποθήκευση ποσού",
                use_container_width=True,
            )

        if save_amount:
            existing_setting = (
                sb.table("player_payment_settings")
                .select("player_id")
                .eq("player_id", amount_pid)
                .execute()
                .data
            )

            payload = {
                "player_id": amount_pid,
                "monthly_amount": float(monthly_amount),
                "updated_by": st.session_state.user.id,
            }

            if existing_setting:
                (
                    sb.table("player_payment_settings")
                    .update(payload)
                    .eq("player_id", amount_pid)
                    .execute()
                )
            else:
                sb.table("player_payment_settings").insert(
                    payload
                ).execute()

            st.success("Το μηνιαίο ποσό αποθηκεύτηκε.")
            st.rerun()

    with tab_history:
        st.subheader("Ιστορικό πληρωμών")

        history_label = st.selectbox(
            "Παίκτης",
            list(label_to_id.keys()),
            key="payment_history_player",
        )

        history_pid = label_to_id[history_label]

        history_rows = [
            r
            for r in payment_rows
            if r.get("player_id") == history_pid
        ]

        if history_rows:
            display_rows = []

            for r in history_rows:
                recorder = r.get("profiles") or {}

                display_rows.append(
                    {
                        "Νο": player_by_id.get(history_pid, {}).get("jersey_number") or "—",
                        "Ημερομηνία": format_date(
                            r.get("paid_on")
                        ),
                        "Ποσό": format_money(r.get("amount")),
                        "Σημείωση": r.get("note") or "",
                        "Καταχώρηση από": recorder.get(
                            "full_name"
                        ) or "—",
                    }
                )

            st.dataframe(
                pd.DataFrame(display_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Δεν έχει καταχωρηθεί πρώτη πληρωμή για αυτόν τον παίκτη."
            )

    with tab_edit:
        st.subheader("Edit / Διαγραφή πληρωμής")

        if not payment_rows:
            st.info("Δεν υπάρχουν πληρωμές.")
        else:
            payment_options = {}

            for r in payment_rows:
                p = player_by_id.get(r.get("player_id"))

                if not p:
                    continue

                label = (
                    f'{player_short_name(p)} · '
                    f'{format_date(r.get("paid_on"))} · '
                    f'{format_money(r.get("amount"))}'
                )

                payment_options[f"{label} · {r['id'][:8]}"] = r

            if not payment_options:
                st.info("Δεν υπάρχουν διαθέσιμες πληρωμές για επεξεργασία.")
            else:
                selected_payment_label = st.selectbox(
                    "Επίλεξε πληρωμή",
                    list(payment_options.keys()),
                    key="edit_payment_select",
                )

                selected_payment = payment_options[selected_payment_label]
                selected_payment_player = player_by_id.get(
                    selected_payment.get("player_id")
                )

                with st.form("edit_payment_form"):
                    st.text_input(
                        "Παίκτης",
                        value=player_short_name(selected_payment_player),
                        disabled=True,
                    )

                    edit_amount = st.number_input(
                        "Ποσό (€)",
                        min_value=0.01,
                        value=float(selected_payment.get("amount") or 0),
                        step=5.0,
                    )

                    edit_paid_on = st.date_input(
                        "Ημερομηνία πληρωμής",
                        value=pd.to_datetime(
                            selected_payment.get("paid_on")
                        ).date(),
                        format="DD/MM/YYYY",
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
                    (
                        sb.table("payments")
                        .update(
                            {
                                "amount": float(edit_amount),
                                "paid_on": str(edit_paid_on),
                                "note": edit_note.strip() or None,
                            }
                        )
                        .eq("id", selected_payment["id"])
                        .execute()
                    )

                    st.success("Η πληρωμή ενημερώθηκε.")
                    st.rerun()

                st.divider()
                st.subheader("Οριστική διαγραφή πληρωμής")

                confirm_payment_delete = st.checkbox(
                    "Επιβεβαίωση διαγραφής",
                    key=f"confirm_payment_delete_{selected_payment['id']}",
                )

                if st.button(
                    "Διαγραφή πληρωμής",
                    type="primary",
                    disabled=not confirm_payment_delete,
                    use_container_width=True,
                ):
                    (
                        sb.table("payments")
                        .delete()
                        .eq("id", selected_payment["id"])
                        .execute()
                    )

                    st.success("Η πληρωμή διαγράφηκε οριστικά.")
                    st.rerun()


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

    st.caption(
        f"Εγκεκριμένοι λογαριασμοί: {len(profiles)} / 10"
    )

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
            st.error(
                "Έχει συμπληρωθεί το όριο των 10 λογαριασμών."
            )

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

                st.success("Ο χρήστης δημιουργήθηκε.")
                st.rerun()

            except Exception as e:
                st.error(
                    f"Δεν δημιουργήθηκε ο χρήστης: {e}"
                )

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

            st.success("Τα δικαιώματα ενημερώθηκαν.")
            st.rerun()


st.caption(APP_NAME)
