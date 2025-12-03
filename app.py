import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from st_aggrid import AgGrid, GridUpdateMode, GridOptionsBuilder

# -------------------------------------------------------------------
# 1. إعداد قاعدة البيانات وتخزين البيانات الأولية
# -------------------------------------------------------------------

DB_NAME = "projects.db"
CSV_FILE = "projects.csv"

# وظيفة لربط قاعدة البيانات
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

# وظيفة لتهيئة الجدول وتحميل البيانات من CSV (تنفذ مرة واحدة)
def setup_database():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # قراءة البيانات من الملف
        df = pd.read_csv(CSV_FILE)
        df.columns = df.columns.str.strip()
        
        # تخزين البيانات في جدول جديد (استبدال إذا كان موجوداً)
        df.to_sql("projects", conn, if_exists="replace", index=False)
        st.success("✅ تم تحميل بيانات المشاريع بنجاح إلى قاعدة البيانات.")
    except FileNotFoundError:
        st.error(f"⚠️ لم يتم العثور على ملف البيانات {CSV_FILE}. الرجاء التأكد من وجوده.")
    except Exception as e:
        st.error(f"⚠️ حدث خطأ أثناء تحميل البيانات: {e}")
    conn.close()

# تهيئة قاعدة البيانات عند بدء التشغيل
setup_database()

# -------------------------------------------------------------------
# 2. وظائف القراءة والكتابة
# -------------------------------------------------------------------

def get_projects_df():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    
    # تحويل الأعمدة الرقمية والتواريخ كما فعلنا سابقاً
    cols_to_clean = ['التكلفة التقديرية', 'قيمة العقد / العقود', 'قيمة المخالصة']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'التكلفة التقديرية' in df.columns and 'قيمة العقد / العقود' in df.columns:
        df['فارق الميزانية'] = df['التكلفة التقديرية'] - df['قيمة العقد / العقود']
        df['حالة الميزانية'] = df['فارق الميزانية'].apply(lambda x: 'وفر ✅' if x >= 0 else 'تجاوز 🔻')

    return df

def update_project(row_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # سنستخدم "رقم العملية الشرائية" كمفتاح فريد للتحديث
    unique_id = row_data['رقم العملية الشرائية']
    
    # بناء جملة التحديث SQL (يجب أن تتضمن كل الأعمدة المحدثة)
    # *ملاحظة: هذا مثال جزئي، يجب تضمين جميع الأعمدة المراد تحديثها في جملة SQL*
    update_query = f"""
    UPDATE projects SET
        "اسم العملية الشرائية" = ?,
        "المقاول" = ?,
        "التكلفة التقديرية" = ?,
        "قيمة العقد / العقود" = ?,
        "ملاحظات" = ?
    WHERE "رقم العملية الشرائية" = ?
    """
    
    # هنا يجب تمرير البيانات بالترتيب الصحيح
    cursor.execute(update_query, (
        row_data['اسم العملية الشرائية'], 
        row_data['المقاول'], 
        row_data['التكلفة التقديرية'], 
        row_data['قيمة العقد / العقود'], 
        row_data['ملاحظات'],
        unique_id
    ))
    
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# 3. واجهة الإدارة والمصادقة (Authentication)
# -------------------------------------------------------------------

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    
def login_form():
    st.sidebar.title("🔐 دخول المسؤول")
    with st.sidebar.form("login_form"):
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول")
        
        # كلمة مرور بسيطة للمثال
        ADMIN_PASSWORD = "12345" 
        
        if submitted:
            if password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.sidebar.success("تم تسجيل الدخول بنجاح!")
                st.rerun()
            else:
                st.sidebar.error("كلمة المرور غير صحيحة.")

def admin_panel(df):
    st.title("🛡️ لوحة تحكم المسؤول (تعديل البيانات)")
    st.warning("لتعديل البيانات، قم بالضغط مرتين على الخلية المراد تغييرها ثم اضغط 'حفظ التعديلات'.")

    # إعداد جدول AgGrid التفاعلي
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_columns(df.columns.tolist(), editable=True, groupable=True)
    gb.configure_grid_options(domLayout='normal')
    
    gridOptions = gb.build()
    
    grid_response = AgGrid(
        df, 
        gridOptions=gridOptions, 
        data_return_mode='AS_INPUT', 
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True, 
        enable_enterprise_modules=False,
        height=500, 
        width='100%',
        reload_data=True
    )

    # حفظ التعديلات
    if st.button("💾 حفظ التعديلات على قاعدة البيانات"):
        if grid_response['data'] is not None:
            updated_df = pd.DataFrame(grid_response['data'])
            
            # تحديد الأعمدة التي تم تعديلها وحفظها
            for index, row in updated_df.iterrows():
                # *ملاحظة هامة: في بيئة حقيقية، يجب مقارنة التعديلات وحفظ الصفوف المحدثة فقط*
                try:
                    update_project(row) # تمرير الصف بالكامل لوظيفة التحديث
                except Exception as e:
                    st.error(f"خطأ في تحديث الصف رقم {index}: {e}")
                    
            st.success("تم حفظ جميع التعديلات بنجاح!")
            st.rerun()


# -------------------------------------------------------------------
# 4. التطبيق الرئيسي (العرض بناءً على حالة تسجيل الدخول)
# -------------------------------------------------------------------

df = get_projects_df()

if st.session_state.logged_in:
    admin_panel(df)
    if st.sidebar.button("تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()
else:
    # عرض لوحة القيادة العامة والبحث (نفس الكود من الرد السابق)
    st.title("لوحة قيادة المشاريع (عرض فقط)")
    
    # هنا يتم عرض الفلاتر والرسوم البيانية التفاعلية كما في الرد السابق
    # (تم اختصارها هنا لتركيز الكود على وظائف الإدارة)
    st.subheader("📊 إجمالي قيمة العقود")
    total_contract = df['قيمة العقد / العقود'].sum()
    st.metric("المجموع الكلي", f"{total_contract:,.0f} دولار")
    
    st.subheader("🔍 الجدول للبحث والاستعلام")
    st.dataframe(df, use_container_width=True)
    
    login_form()
