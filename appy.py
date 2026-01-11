import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعدادات المظهر الفخم (نفس الواجهة السابقة) ---
Z_COPPER = "#BC846C"   # برونزي
Z_DARK = "#1B3022"     # أخضر غامق
Z_LIGHT = "#F4F1EE"    # خلفية فاتحة

st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; }}
    .stApp {{ background-color: {Z_LIGHT}; }}
    h1, h2, h3, p, span, label, .stMarkdown {{ color: {Z_DARK} !important; }}
    .main-card {{ background: white; padding: 25px; border-radius: 15px; border-right: 12px solid {Z_COPPER}; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    .val-box {{ color: {Z_COPPER} !important; font-size: 24px; font-weight: 800; }}
    .label-text {{ font-weight: bold; font-size: 16px; opacity: 0.8; }}
    .stTabs [data-baseweb="tab"] p {{ color: {Z_DARK} !important; font-weight: bold; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. إعداد السحابة ---
@st.cache_resource
def init_firebase():
    try:
        if not firebase_admin._apps:
            if os.path.exists('firebase_key.json'):
                cred = credentials.Certificate('firebase_key.json')
                firebase_admin.initialize_app(cred)
        return firestore.client()
    except: return None

db = init_firebase()

# --- 3. معالجة البيانات (التحميل الذكي لضمان السرعة) ---
@st.cache_data(show_spinner="جاري تحديث بيانات المخطط...")
def load_combined_data():
    inventory = {}
    
    # أ. قراءة ملف "نموذج المخطط" (المرجع الشامل)
    master_files = glob.glob("*نموذج المخطط*.pdf")
    if master_files:
        with pdfplumber.open(master_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            price_raw = "".join(re.findall(r'\d+', str(r[6]))) if len(r)>6 and r[6] else "0"
                            inventory[uid] = {
                                'id': uid, 'blk': r[1], 'area': r[4],
                                'price': float(price_raw) if price_raw else 0.0,
                                'status': 'مباع' # الافتراضي مباع
                            }
    
    # ب. قراءة ملف "الشاغر" لتحديث الحالة إلى "متاح"
    vacant_files = glob.glob("*الشاغرة*.pdf")
    if vacant_files:
        with pdfplumber.open(vacant_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            if uid in inventory:
                                inventory[uid]['status'] = 'متاح'
    return inventory

# تحميل البيانات في الذاكرة ليكون البحث لحظياً
units_inventory = load_combined_data()

# --- 4. الواجهة الرئيسية ---
st.markdown(f"<h1 style='text-align:center;'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["💎 محرك البحث مبيعات", "⚙️ لوحة تحكم السحابة"])

with tab1:
    search_id = st.text_input("🔍 ادخل رقم القطعة:")
    if search_id:
        uid = str(search_id).strip()
        if uid in units_inventory:
            unit = units_inventory[uid]
            
            # جلب الحالة من السحابة (الأولوية القصوى)
            current_status = unit['status']
            if db:
                try:
                    doc = db.collection('units').document(uid).get(timeout=1)
                    if doc.exists: current_status = doc.to_dict().get('status', current_status)
                except: pass

            # تحديد لون الحالة
            status_color = "#28a745" if current_status == "متاح" else "#dc3545"
            if current_status == "محجوز": status_color = "#ffc107"

            st.markdown(f"""
            <div class="main-card">
                <h2 style="margin-bottom:20px;">القطعة رقم {unit['id']} <span style="color:{status_color};">({current_status})</span></h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                    <div><span class="label-text">رقم البلك:</span><br><span class="val-box">{unit['blk']}</span></div>
                    <div><span class="label-text">المساحة:</span><br><span class="val-box">{unit['area']} م²</span></div>
                    <div><span class="label-text">السعر الأساسي:</span><br><span class="val-box">{unit['price']:,.2f} ريال</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if current_status == "متاح":
                st.write("---")
                col_c1, col_c2 = st.columns(2)
                with col_c1: cust_name = st.text_input("👤 اسم العميل الموقر:")
                with col_c2: discount_pct = st.number_input("📉 نسبة الخصم (%):", 0.0, 100.0, 0.0)

                final_p = unit['price'] * (1 - discount_pct/100)
                total_w_fees = final_p + 2000
                
                st.success(f"الصافي: {final_p:,.2f} ريال | الإجمالي مع السعي: {total_w_fees:,.2f} ريال")

                if cust_name:
                    if st.button("📄 إصدار عرض السعر"):
                        template_path = "projecttemplate.docx"
                        if os.path.exists(template_path):
                            doc_tpl = DocxTemplate(template_path)
                            doc_tpl.render({
                                'date': datetime.now().strftime("%Y/%m/%d"),
                                'name': cust_name, 'id': unit['id'], 'blk': unit['blk'],
                                'area': unit['area'], 'price': f"{final_p:,.2f}",
                                'fees': "2,000.00", 'total': f"{total_w_fees:,.2f}",
                                'desc': f"قطعة {unit['id']} بلك {unit['blk']} بمساحة {unit['area']}"
                            })
                            out_io = io.BytesIO(); doc_tpl.save(out_io)
                            st.download_button(f"📥 تحميل عرض {cust_name}", out_io.getvalue(), f"عرض_{cust_name}.docx")
        else:
            st.error("❌ هذه القطعة غير موجودة في المخطط العام.")

with tab2:
    st.subheader("إدارة حالة الوحدات سحابياً")
    if db:
        u_id = st.text_input("ادخل رقم القطعة لتحديثها:")
        new_status = st.selectbox("الحالة الجديدة:", ["متاح", "مباع", "محجوز"])
        if st.button("حفظ التغييرات في السحابة"):
            db.collection('units').document(str(u_id)).set({'status': new_status}, merge=True)
            st.success(f"✅ تم تحديث {u_id} إلى {new_status}")
            st.cache_data.clear() # لمسح الكاش وتحديث البيانات فوراً
    else:
        st.error("السحابة غير متصلة.")
