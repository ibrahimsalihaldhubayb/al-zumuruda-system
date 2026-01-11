import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate

# --- 1. إعدادات التنسيق والألوان ---
Z_COPPER = "#BC846C" 
Z_DARK = "#1B3022" 
Z_LIGHT = "#F4F1EE"

st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")

# تطبيق التنسيق العربي وإصلاح الأرقام المعكوسة
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; }}
    .stApp {{ background-color: {Z_LIGHT}; }}
    .main-card {{ background: white; padding: 25px; border-radius: 15px; border-right: 10px solid {Z_COPPER}; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-top: 20px; }}
    .val-box {{ color: {Z_COPPER}; font-size: 22px; font-weight: bold; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. دوال البحث (المحسنة) ---
def find_any_pdf():
    files = glob.glob("*.pdf")
    return files[0] if files else None

def get_unit_data(target_id):
    pdf_path = find_any_pdf()
    if not pdf_path: return None
    target_id = str(target_id).strip()
    try:
        with pdfplumber.open(pdf_path) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0] and str(r[0]).strip() == target_id:
                            # استخراج السعر وتنظيفه
                            price_str = "".join(re.findall(r'\d+', str(r[6]))) if len(r) > 6 else "0"
                            return {
                                'id': r[0],
                                'blk': r[1],
                                'area': r[4],
                                'price': float(price_str) if price_str else 0.0,
                                'desc': f"القطعة رقم {r[0]} في البلك رقم {r[1]} بمساحة {r[4]} م٢"
                            }
    except: return None
    return None

def format_money(amount):
    return "{:,.2f}".format(amount)

# --- 3. واجهة المستخدم ---
st.markdown(f"<h1 style='text-align:center; color:{Z_DARK};'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)

search_id = st.text_input("🔍 ادخل رقم القطعة للبحث:")

if search_id:
    res = get_unit_data(search_id)
    
    if res:
        st.markdown(f"""
        <div class="main-card">
            <h2 style="color:{Z_DARK};">تفاصيل القطعة رقم {res['id']}</h2>
            <div style="display: flex; justify-content: space-between; margin-top: 20px;">
                <div>رقم البلك: <span class="val-box">{res['blk']}</span></div>
                <div>المساحة: <span class="val-box">{res['area']} م²</span></div>
                <div>السعر الأساسي: <span class="val-box">{format_money(res['price'])} ريال</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- الحاسبة ---
        st.markdown("### 🧮 حاسبة العرض")
        col1, col2 = st.columns(2)
        with col1:
            cust_name = st.text_input("👤 اسم العميل الموقر:")
        with col2:
            discount_pct = st.number_input("📉 نسبة الخصم (%):", min_value=0.0, max_value=100.0, step=0.1)

        final_price = res['price'] * (1 - discount_pct/100)
        office_fees = 2000.0
        total_amount = final_price + office_fees

        st.markdown(f"""
        <div style="background:{Z_DARK}; color:white; padding:15px; border-radius:10px; text-align:center; margin-top:20px;">
            <h3 style="margin:0;">صافي السعر بعد الخصم: {format_money(final_price)} ريال</h3>
            <p style="margin:0; opacity:0.8;">إجمالي السعر مع السعي (2,000 ريال): {format_money(total_amount)} ريال</p>
        </div>
        """, unsafe_allow_html=True)

        # --- إنشاء عرض السعر (الوورد) ---
        if cust_name:
            template_path = "projecttemplate.docx"
            if os.path.exists(template_path):
                try:
                    doc = DocxTemplate(template_path)
                    context = {
                        'date': datetime.now().strftime("%Y/%m/%d"),
                        'name': cust_name,
                        'id': res['id'],
                        'blk': res['blk'],
                        'area': res['area'],
                        'price': format_money(final_price),
                        'fees': format_money(office_fees),
                        'total': format_money(total_amount),
                        'desc': res['desc'] # وصف القطعة
                    }
                    doc.render(context)
                    out_io = io.BytesIO()
                    doc.save(out_io)
                    
                    st.download_button(
                        label=f"📥 تحميل عرض سعر {cust_name}",
                        data=out_io.getvalue(),
                        file_name=f"عرض_سعر_{res['id']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                except Exception as e:
                    st.error(f"حدث خطأ في ملف الوورد: {e}")
            else:
                st.warning("⚠️ ملف projecttemplate.docx غير موجود في المستودع")
    else:
        st.error("❌ لم يتم العثور على هذه القطعة، تأكد من الرقم المكتوب.")
