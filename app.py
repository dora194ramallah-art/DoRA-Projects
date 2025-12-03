import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ---------------------------------------------------------
# 1. إعداد الصفحة وتنسيق الواجهة
# ---------------------------------------------------------
st.set_page_config(page_title="نظام مشاريع المخيمات", layout="wide", page_icon="🏗️")

# تنسيق CSS مخصص لدعم العربية (RTL)
st.markdown("""
<style>
    .main {direction: rtl; text-align: right;}
    div.block-container {padding-top: 2rem;}
    h1, h2, h3 {text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    .stMetric {text-align: right !important; direction: rtl;}
    /* محاولة لضبط اتجاه الجداول */
    .stDataFrame {direction: rtl;}
</style>
""", unsafe_allow_html=True)

st.title("🏗️ لوحة القيادة الذكية - مشاريع المخيمات 2025")

# ---------------------------------------------------------
# 2. تحميل وتنظيف البيانات
# ---------------------------------------------------------
@st.cache_data
def load_data():
    # قراءة الملف (يفترض أن الملف محفوظ باسم projects.csv)
    try:
        df = pd.read_csv("projects.csv") 
    except:
        # محاولة قراءة ملف الاكسل مباشرة اذا لم يتم التحويل ل csv
        # df = pd.read_excel("projects.xlsx")
        st.error("لم يتم العثور على الملف. الرجاء التأكد من وجود ملف باسم projects.csv")
        return pd.DataFrame()

    # تنظيف أسماء الأعمدة (إزالة المسافات الزائدة)
    df.columns = df.columns.str.strip()

    # تحويل الأعمدة الرقمية (التكلفة والعقود)
    cols_to_clean = ['التكلفة التقديرية', 'قيمة العقد / العقود', 'قيمة المخالصة']
    for col in cols_to_clean:
        if col in df.columns:
            # إزالة النصوص مثل "دولار" أو الفواصل
            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # تحويل التواريخ
    date_cols = ['تاريخ المباشرة', 'تاريخ الاستلام الابتدائي', 'تاريخ التقدم بالاقفال']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)

    # حسابات إضافية مفيدة للتحليل
    if 'التكلفة التقديرية' in df.columns and 'قيمة العقد / العقود' in df.columns:
        df['فارق الميزانية'] = df['التكلفة التقديرية'] - df['قيمة العقد / العقود']
        df['حالة الميزانية'] = df['فارق الميزانية'].apply(lambda x: 'وفر ✅' if x >= 0 else 'تجاوز 🔻')

    return df

df = load_data()

if df.empty:
    st.stop()

# ---------------------------------------------------------
# 3. الشريط الجانبي (فلاتر البحث)
# ---------------------------------------------------------
st.sidebar.header("🔍 أدوات التصفية")

# فلتر حسب المقاول
contractors = st.sidebar.multiselect(
    "المقاول",
    options=df['المقاول'].unique(),
    default=df['المقاول'].unique()
)

# فلتر حسب مصدر التمويل
funding_sources = st.sidebar.multiselect(
    "مصدر التمويل",
    options=df['مصدر التمويل'].unique(),
    default=df['مصدر التمويل'].unique()
)

# فلتر حالة الإقفال (بناء على عمود التقدم بالاقفال)
if 'التقدم بالاقفال' in df.columns:
    status_filter = st.sidebar.multiselect(
        "حالة الإقفال",
        options=df['التقدم بالاقفال'].unique(),
        default=df['التقدم بالاقفال'].unique()
    )
    df_selection = df.query("`التقدم بالاقفال` == @status_filter")
else:
    df_selection = df

# تطبيق باقي الفلاتر
df_selection = df_selection.query(
    "`المقاول` == @contractors & `مصدر التمويل` == @funding_sources"
)

# ---------------------------------------------------------
# 4. مؤشرات الأداء (KPIs)
# ---------------------------------------------------------
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("عدد المشاريع", len(df_selection))

with col2:
    total_estimated = df_selection['التكلفة التقديرية'].sum()
    st.metric("إجمالي التكلفة التقديرية", f"${total_estimated:,.0f}")

with col3:
    total_contract = df_selection['قيمة العقد / العقود'].sum()
    delta_val = total_estimated - total_contract
    st.metric("إجمالي قيمة العقود", f"${total_contract:,.0f}", delta=f"{delta_val:,.0f} (وفر/عجز)")

with col4:
    # عدد المشاريع المقفلة (التي تحتوي على "نعم" أو قيمة في تاريخ الإقفال)
    closed_projects = df_selection[df_selection['التقدم بالاقفال'].astype(str).str.contains('نعم', na=False)].shape[0]
    st.metric("المشاريع المنجزة/المقفلة", closed_projects)

# ---------------------------------------------------------
# 5. الرسوم البيانية والتحليل
# ---------------------------------------------------------
st.markdown("### 📊 التحليل المالي والزمني")

row1_col1, row1_col2 = st.columns([2, 1])

with row1_col1:
    # رسم بياني يقارن التكلفة التقديرية بقيمة العقد لكل مشروع
    st.subheader("مقارنة: التكلفة التقديرية vs قيمة العقد")
    
    # تحضير البيانات للرسم (Melt)
    df_melted = df_selection.melt(id_vars=['اسم العملية الشرائية'], 
                                  value_vars=['التكلفة التقديرية', 'قيمة العقد / العقود'],
                                  var_name='نوع التكلفة', value_name='القيمة')
    
    fig_bar = px.bar(df_melted, x='اسم العملية الشرائية', y='القيمة', color='نوع التكلفة', barmode='group',
                     color_discrete_map={'التكلفة التقديرية': '#abb8c3', 'قيمة العقد / العقود': '#0068c9'})
    st.plotly_chart(fig_bar, use_container_width=True)

with row1_col2:
    # توزيع المشاريع حسب مصدر التمويل
    st.subheader("توزيع التمويل")
    fig_pie = px.pie(df_selection, values='قيمة العقد / العقود', names='مصدر التمويل', donut=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

# ---------------------------------------------------------
# 6. الجدول التفصيلي للبيانات
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📋 سجل العمليات التفصيلي")

# تلوين الخلايا بناءً على حالة الميزانية
def highlight_budget(val):
    if val == 'وفر ✅':
        return 'background-color: #d4edda; color: green'
    elif val == 'تجاوز 🔻':
        return 'background-color: #f8d7da; color: red'
    return ''

# عرض الجدول مع إمكانية التوسيع
with st.expander("اضغط هنا لعرض/إخفاء الجدول الكامل", expanded=True):
    st.dataframe(
        df_selection.style.map(highlight_budget, subset=['حالة الميزانية'])
        .format({'التكلفة التقديرية': '{:,.0f}', 'قيمة العقد / العقود': '{:,.0f}', 'فارق الميزانية': '{:,.0f}'}),
        use_container_width=True,
        height=400
    )

# زر التحميل
csv = df_selection.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    "📥 تحميل التقرير الحالي (Excel/CSV)",
    csv,
    "report.csv",
    "text/csv",
    key='download-csv'
)
