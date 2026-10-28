import fitz,re,glob,os,sys,json
from pdf_table_dzial import parse_cell
ROOT='../../sources/pdf_urzad'
def rows(pdf):
    doc=fitz.open(pdf)
    for pi,page in enumerate(doc):
        dr=page.get_drawings()
        imgs=[fitz.Rect(i['bbox']) for i in page.get_image_info()]
        for t in page.find_tables().tables:
            for row,vals in zip(t.rows,t.extract()):
                cs=[c for c in row.cells if c]
                if len(cs)<4 or not vals: continue
                m=re.fullmatch(r"(\d{1,3})\.?",(vals[0] or '').strip())
                if not m: continue
                ci=max(range(len(row.cells)),key=lambda i:(row.cells[i][2]-row.cells[i][0]) if row.cells[i] else -1)
                cell=fitz.Rect(row.cells[ci])
                inner=fitz.Rect(cell.x0+3,cell.y0+3,cell.x1-3,cell.y1-3)
                g=[fitz.Rect(d['rect']) for d in dr if inner.contains(fitz.Rect(d['rect'])) and (d['rect'].width>2 or d['rect'].height>2)]
                im=[i for i in imgs if cell.intersects(i)]
                yield pi,page,int(m.group(1)),cell,vals[ci] or '',len(g),len(im),vals[-1]
if __name__=='__main__':
    tot=0
    for f in sorted(glob.glob(ROOT+'/**/*.pdf',recursive=True)):
        c=0;ex=[]
        for pi,page,nr,cell,txt,ng,ni,k in rows(f):
            if ng>=3 or ni:
                c+=1; ex.append((nr,ng,ni))
        tot+=c
        if c: print(os.path.basename(f)[:40],'|',f.replace(chr(92),'/').split('pdf_urzad/')[1][:40],c,ex[:5])
    print(tot)
