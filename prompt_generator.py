# -*- coding: utf-8 -*-
# 이 스크립트를 실행하기 전에 'python-docx' 라이브러리를 설치해야 합니다.
# 터미널(CMD)에 다음 명령어를 입력하여 설치하세요:
# pip install python-docx

import os
import re
import sys
import json
from docx import Document
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# ==============================================================================
# 기본 프롬프트 템플릿 및 설정 (이 값들은 초기화 또는 설정 파일 없을 때 사용)
# ==============================================================================

CONFIG_FILE_NAME = "CustomPrompt.json"

ORIGINAL_DEFAULT_PROMPT_1 = """
너는 전문 번역가야.
직전의 문맥을 파악하여 아래 영문 원본을 한국어로 번역해 줘.
용어 번역시 'Translation glossary.txt' 파일의 용어에 맞추어 번역해줘.
법률/규정 문서에 사용될 수 있도록, 전문적이고 격식 있는 톤을 유지해야 해.

[영어 원본]
{english_chunk}
[/영어 원본]
"""

ORIGINAL_DEFAULT_PROMPT_2 = """
너는 최고의 한국어 법률 번역 전문가야.
직전의 문맥을 파악하여 아래의 <영어 원문>과 AI가 번역한 <초벌 번역문>을 비교해서, 번역이 어색하거나 오역된 부분을 찾아 수정하고, 더 자연스럽고 전문적인 한국어 법률 문서로 개선해 줘.
용어 번역시 'Translation glossary.txt' 파일의 번역용어에 맞추어 번역해줘.

[영어 원문]
{english_chunk}
[/영어 원본]

[초벌 번역문]
{korean_draft}
[/초벌 번역문]


결과물은 아래 형식에 맞춰서, 개선된 번역문과 수정 이유를 명확히 구분해서 작성해줘.

---번역문 시작---
[여기에 개선된 번역문만 작성]
---번역문 끝---

---수정 이유 시작---
[여기에 수정 이유만 작성]
---수정 이유 끝---
"""

DEFAULT_PROMPT_3_SUGGESTION = """
너는 용어 추출 전문가야.
아래 <영어 원문>과 <최종 한국어 번역문>을 비교 분석해서, 'Translation glossary.txt' 파일에 추가할 만한 핵심 용어들을 추출해 줘.
결과는 반드시 '[원문 용어] - [번역 용어]' 형식으로, 한 줄에 하나씩만 정리해서 보여줘. 다른 설명은 필요 없어.

[영어 원본]
{english_chunk}
[/영어 원본]

[최종 한국어 번역문]
{final_korean_text}
[/최종 한국어 번역문]
"""


# ==============================================================================
# 핵심 로직
# ==============================================================================

def get_config_path():
    """설정 파일의 경로를 반환합니다. (EXE 호환)"""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(application_path, CONFIG_FILE_NAME)

def load_settings_from_json():
    """JSON 설정 파일에서 프롬프트와 설정을 불러옵니다."""
    config_path = get_config_path()
    defaults = {
        "prompt1": ORIGINAL_DEFAULT_PROMPT_1.strip(),
        "prompt2": ORIGINAL_DEFAULT_PROMPT_2.strip(),
        "chunk_size": 400
    }
    if not os.path.exists(config_path):
        return defaults

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            defaults.update(config)
            return defaults
    except (json.JSONDecodeError, Exception) as e:
        messagebox.showwarning("설정 파일 오류", f"설정 파일({CONFIG_FILE_NAME})을 읽는 중 오류가 발생했습니다.\n기본 설정으로 시작합니다.\n\n오류: {e}")
        return defaults

def save_settings_to_json(settings):
    """설정을 JSON 파일에 저장합니다."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        messagebox.showerror("설정 저장 오류", f"설정 파일 저장 중 오류가 발생했습니다:\n{e}")
        return False

def chunk_document_by_word_count(doc_path, target_words=400):
    try:
        doc = Document(doc_path)
        chunks = []
        current_chunk_paragraphs = []
        current_word_count = 0
        for para in doc.paragraphs:
            paragraph_text = para.text
            word_count = len(paragraph_text.split())
            if current_word_count > 0 and current_word_count + word_count > target_words:
                chunks.append("\n".join(current_chunk_paragraphs))
                current_chunk_paragraphs = []
                current_word_count = 0
            current_chunk_paragraphs.append(paragraph_text)
            current_word_count += word_count
        if current_chunk_paragraphs:
            chunks.append("\n".join(current_chunk_paragraphs))
        return chunks
    except Exception as e:
        messagebox.showerror("파일 오류", f"문서 파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

def load_glossary(file_path):
    if not file_path or not os.path.exists(file_path): return {}
    try:
        glossary = {}
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                match = re.match(r'\[(.*?)\]\s*-\s*\[(.*?)\]', line)
                if match:
                    eng, kor = match.groups()
                    glossary[eng.strip()] = kor.strip()
                elif ' - ' in line:
                    parts = [p.strip() for p in line.rsplit(' - ', 1)]
                    if len(parts) == 2 and parts[0] and parts[1]:
                        glossary[parts[0]] = parts[1]
        return glossary
    except Exception as e:
        messagebox.showwarning("용어집 오류", f"용어집 파일을 읽는 중 오류가 발생했습니다: {e}")
        return {}

def save_glossary(file_path, glossary_data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for eng, kor in sorted(glossary_data.items()):
                f.write(f"[{eng}] - [{kor}]\n")
        return True
    except Exception as e:
        messagebox.showerror("저장 오류", f"용어집 파일 저장 중 오류가 발생했습니다: {e}")
        return False

# ==============================================================================
# GUI 클래스
# ==============================================================================

class PromptSettingsWindow(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.parent_app = parent_app
        self.title("설정")
        self.geometry("700x700")
        self.transient(parent_app.root); self.grab_set()
        self.setup_widgets()
        self.load_settings()

    def setup_widgets(self):
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(fill="both", expand=True)
        
        chunk_frame = ttk.LabelFrame(main_frame, text="번역 단위 설정", padding="10"); chunk_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(chunk_frame, text="청크 크기 (단어 수 기준):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.chunk_size_var = tk.StringVar()
        ttk.Entry(chunk_frame, textvariable=self.chunk_size_var, width=10).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(chunk_frame, text="(기본값: 400)").grid(row=0, column=2, sticky="w", padx=5)

        prompt_frame = ttk.LabelFrame(main_frame, text="프롬프트 템플릿 설정", padding="10"); prompt_frame.pack(fill="both", expand=True, pady=10)
        
        # --- 수정: 레이아웃 코드 개선 ---
        label1 = ttk.Label(prompt_frame, text="1단계: 초벌 번역 프롬프트", font=("Malgun Gothic", 11, "bold"))
        label1.pack(anchor="w")
        
        self.prompt1_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=8, font=("Malgun Gothic", 10))
        self.prompt1_text.pack(fill="both", expand=True, pady=5)
        
        label1_vars = ttk.Label(prompt_frame, text="사용 가능 변수: {english_chunk}", foreground="blue")
        label1_vars.pack(anchor="w", pady=(0, 15))
        
        label2 = ttk.Label(prompt_frame, text="2단계: 개선 번역 프롬프트", font=("Malgun Gothic", 11, "bold"))
        label2.pack(anchor="w")
        
        self.prompt2_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=8, font=("Malgun Gothic", 10))
        self.prompt2_text.pack(fill="both", expand=True, pady=5)
        
        label2_vars = ttk.Label(prompt_frame, text="사용 가능 변수: {english_chunk}, {korean_draft}", foreground="blue")
        label2_vars.pack(anchor="w")

        button_frame = ttk.Frame(main_frame); button_frame.pack(fill="x", pady=10)
        ttk.Button(button_frame, text="저장", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="초기화", command=self.reset_prompts).pack(side="right", padx=5)
        ttk.Button(button_frame, text="취소", command=self.destroy).pack(side="right")

    def load_settings(self):
        # --- 수정: 데이터 로딩 안정성 강화 ---
        chunk_size = self.parent_app.chunk_size if self.parent_app.chunk_size is not None else 400
        prompt1 = self.parent_app.prompt_1_template if self.parent_app.prompt_1_template is not None else ""
        prompt2 = self.parent_app.prompt_2_template if self.parent_app.prompt_2_template is not None else ""

        self.chunk_size_var.set(str(chunk_size))
        self.prompt1_text.insert("1.0", prompt1)
        self.prompt2_text.insert("1.0", prompt2)

    def save_settings(self):
        try:
            new_chunk_size = int(self.chunk_size_var.get())
            if new_chunk_size <= 0: raise ValueError
        except ValueError:
            return messagebox.showwarning("입력 오류", "청크 크기는 0보다 큰 숫자여야 합니다.", parent=self)

        new_prompt1 = self.prompt1_text.get("1.0", tk.END).strip()
        new_prompt2 = self.prompt2_text.get("1.0", tk.END).strip()
        
        if "{english_chunk}" not in new_prompt1 or "{english_chunk}" not in new_prompt2 or "{korean_draft}" not in new_prompt2:
            return messagebox.showwarning("오류", "프롬프트에 필수 변수가 포함되어 있는지 확인하세요.", parent=self)
        
        new_settings = {
            "prompt1": new_prompt1,
            "prompt2": new_prompt2,
            "chunk_size": new_chunk_size
        }

        if save_settings_to_json(new_settings):
            self.parent_app.prompt_1_template = new_prompt1
            self.parent_app.prompt_2_template = new_prompt2
            self.parent_app.chunk_size = new_chunk_size
            messagebox.showinfo("저장 완료", f"설정이 {CONFIG_FILE_NAME} 파일에 저장되었습니다.", parent=self)
            self.destroy()

    def reset_prompts(self):
        if messagebox.askyesno("프롬프트 초기화", "프롬프트 설정을 기본값으로 되돌리시겠습니까?\n(저장 버튼을 눌러야 최종 적용됩니다.)", parent=self):
            self.prompt1_text.delete("1.0", tk.END); self.prompt1_text.insert("1.0", ORIGINAL_DEFAULT_PROMPT_1.strip())
            self.prompt2_text.delete("1.0", tk.END); self.prompt2_text.insert("1.0", ORIGINAL_DEFAULT_PROMPT_2.strip())

class GlossaryConflictWindow(tk.Toplevel):
    def __init__(self, parent, conflicts):
        super().__init__(parent)
        self.decisions = {}; self.title("용어집 충돌 해결"); self.geometry("800x500")
        self.transient(parent); self.grab_set()
        self.setup_widgets(); self.populate_conflicts(conflicts)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel); self.wait_window(self)

    def setup_widgets(self):
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(fill="both", expand=True)
        ttk.Label(main_frame, text="기존 용어와 충돌하는 항목이 발견되었습니다.", wraplength=780).pack(anchor="w", pady=(0, 10))
        batch_frame = ttk.Frame(main_frame); batch_frame.pack(fill="x", pady=5)
        ttk.Button(batch_frame, text="모두 기존 번역 유지", command=lambda: self.set_all_actions("기존 유지")).pack(side="left", padx=5)
        ttk.Button(batch_frame, text="모두 새 번역으로 업데이트", command=lambda: self.set_all_actions("새로 업데이트")).pack(side="left", padx=5)
        tree_frame = ttk.Frame(main_frame); tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("eng", "old", "new", "action"), show="headings")
        self.tree.heading("eng", text="영어 원문"); self.tree.heading("old", text="기존 번역"); self.tree.heading("new", text="새 번역"); self.tree.heading("action", text="선택")
        self.tree.column("eng", width=200); self.tree.column("old", width=200); self.tree.column("new", width=200); self.tree.column("action", width=120, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_tree_click)
        button_frame = ttk.Frame(main_frame); button_frame.pack(fill="x", pady=10)
        ttk.Button(button_frame, text="결정 사항 적용", command=self.on_confirm).pack(side="right", padx=5)
        ttk.Button(button_frame, text="취소", command=self.on_cancel).pack(side="right")

    def populate_conflicts(self, conflicts):
        for c in conflicts:
            item_id = self.tree.insert("", "end", values=(c['eng'], c['old_kor'], c['new_kor'], "새로 업데이트"))
            self.decisions[item_id] = "새로 업데이트"

    def on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell" and self.tree.identify_column(event.x) == "#4":
            self.edit_action(self.tree.identify_row(event.y))

    def edit_action(self, item_id):
        if hasattr(self, "cb"): self.cb.destroy()
        bbox = self.tree.bbox(item_id, column="action")
        if not bbox: return
        self.cb = ttk.Combobox(self.tree, values=["기존 유지", "새로 업데이트"], state="readonly")
        self.cb.set(self.tree.set(item_id, "action")); self.cb.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3]); self.cb.focus_set()
        def on_select(e): self.tree.set(item_id, "action", self.cb.get()); self.decisions[item_id] = self.cb.get(); self.cb.destroy()
        self.cb.bind("<<ComboboxSelected>>", on_select); self.cb.bind("<FocusOut>", lambda e: self.cb.destroy())

    def set_all_actions(self, action):
        for item_id in self.tree.get_children(): self.tree.set(item_id, "action", action); self.decisions[item_id] = action
    def on_confirm(self):
        self.decisions = [{'eng': self.tree.item(i)['values'][0], 'action': self.decisions.get(i), 'new_kor': self.tree.item(i)['values'][2]} for i in self.tree.get_children()]
        self.destroy()
    def on_cancel(self): self.decisions = None; self.destroy()

class ReviewWindow(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.parent_app = parent_app; self.title("3단계: 번역 검토 및 용어집 업데이트"); self.geometry("900x700")
        self.transient(parent_app.root); self.grab_set(); self.setup_widgets()

    def setup_widgets(self):
        main = ttk.Frame(self, padding="10"); main.pack(fill="both", expand=True)
        top = ttk.Frame(main); top.pack(fill="both", expand=True, pady=(0, 10))
        top.columnconfigure(0, weight=1); top.columnconfigure(1, weight=1); top.rowconfigure(0, weight=1)
        
        f1 = ttk.LabelFrame(top, text="1. 최종 번역문 불일치 검사", padding="10"); f1.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        f1.rowconfigure(1, weight=1); f1.columnconfigure(0, weight=1)
        ttk.Label(f1, text="AI 최종 번역문 붙여넣기:").grid(row=0, column=0, sticky="w")
        self.final_text = scrolledtext.ScrolledText(f1, wrap=tk.WORD, height=8); self.final_text.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        ttk.Button(f1, text="불일치 검사 실행", command=self.check_discrepancies).grid(row=2, column=0, pady=5)
        self.d_list = ttk.Treeview(f1, columns=("term", "status"), show="headings", height=5)
        self.d_list.heading("term", text="용어"); self.d_list.heading("status", text="상태"); self.d_list.column("term", width=200)
        self.d_list.grid(row=3, column=0, sticky="nsew", pady=5)
        
        f2 = ttk.LabelFrame(top, text="2. 신규 용어 추가 (AI 활용)", padding="10"); f2.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        f2.rowconfigure(2, weight=1); f2.columnconfigure(0, weight=1)
        ttk.Button(f2, text="신규 용어 추출 프롬프트 생성", command=self.generate_suggestion_prompt).grid(row=0, column=0, pady=5)
        ttk.Label(f2, text="AI 답변(용어 목록) 붙여넣기:").grid(row=1, column=0, sticky="w")
        self.s_input = scrolledtext.ScrolledText(f2, wrap=tk.WORD, height=8); self.s_input.grid(row=2, column=0, sticky="nsew", pady=(5,0))
        ttk.Button(f2, text="제안 용어 목록 적용", command=self.apply_suggestions).grid(row=3, column=0, pady=5)
        
        ttk.Button(main, text="변경사항 저장 후 닫기", command=self.save_and_close).pack(pady=10, fill="x")

    def extract_translation(self, text):
        match = re.search(r"---번역문 시작---(.*?)---번역문 끝---", text, re.DOTALL)
        return match.group(1).strip() if match else text

    def check_discrepancies(self):
        self.d_list.delete(*self.d_list.get_children())
        text = self.final_text.get("1.0", tk.END)
        if not text.strip(): return messagebox.showwarning("입력 필요", "최종 번역문을 붙여넣어 주세요.", parent=self)
        trans = self.extract_translation(text)
        glossary, chunk = self.parent_app.glossary_data, self.parent_app.chunks[self.parent_app.current_chunk_index]
        mismatches = [f"{e} ({k})" for e, k in glossary.items() if re.search(r'\b' + re.escape(e) + r'\b', chunk, re.I) and k not in trans]
        for term in mismatches: self.d_list.insert("", "end", values=(term, "누락됨"))
        if not mismatches: messagebox.showinfo("검토 완료", "용어집과 충돌하는 항목을 찾지 못했습니다.", parent=self)

    def generate_suggestion_prompt(self):
        text = self.final_text.get("1.0", tk.END).strip()
        if not text: return messagebox.showwarning("입력 필요", "최종 번역문을 붙여넣어 주세요.", parent=self)
        trans = self.extract_translation(text)
        if not trans: return messagebox.showwarning("오류", "AI 답변에서 번역문을 추출할 수 없습니다.", parent=self)
        prompt = DEFAULT_PROMPT_3_SUGGESTION.format(english_chunk=self.parent_app.chunks[self.parent_app.current_chunk_index], final_korean_text=trans)
        pw = tk.Toplevel(self); pw.title("신규 용어 추출 프롬프트"); pw.geometry("600x400")
        ta = scrolledtext.ScrolledText(pw, wrap=tk.WORD); ta.pack(fill="both", expand=True, padx=10, pady=10)
        ta.insert("1.0", prompt)
        ttk.Button(pw, text="클립보드에 복사", command=lambda: self.copy_to_clipboard(prompt, pw)).pack(pady=5)

    def copy_to_clipboard(self, text, parent):
        self.clipboard_clear(); self.clipboard_append(text)
        messagebox.showinfo("복사 완료", "프롬프트가 클립보드에 복사되었습니다.", parent=parent)

    def apply_suggestions(self):
        text = self.s_input.get("1.0", tk.END).strip()
        if not text: return messagebox.showwarning("입력 필요", "AI 답변(용어 목록)을 먼저 붙여넣어 주세요.", parent=self)
        new, conflicts = {}, []
        for line in text.split('\n'):
            if not (line := line.strip()): continue
            eng, kor = None, None
            if m := re.match(r'\[(.*?)\]\s*-\s*\[(.*?)\]', line): eng, kor = m.groups()
            elif ' - ' in line:
                parts = [p.strip() for p in line.rsplit(' - ', 1)]
                if len(parts) == 2 and parts[0] and parts[1]: eng, kor = parts
            if eng and kor:
                eng, kor = eng.strip(), kor.strip()
                if eng in self.parent_app.glossary_data and self.parent_app.glossary_data[eng] != kor:
                    conflicts.append({'eng': eng, 'old_kor': self.parent_app.glossary_data[eng], 'new_kor': kor})
                elif eng not in self.parent_app.glossary_data and eng not in new: new[eng] = kor
        
        updated = 0
        if conflicts:
            decisions = GlossaryConflictWindow(self, conflicts).decisions
            if decisions is None: return messagebox.showinfo("알림", "용어 추가 작업이 취소되었습니다.", parent=self)
            for d in decisions:
                if d['action'] == '새로 업데이트':
                    self.parent_app.glossary_data[d['eng']] = d['new_kor']; updated += 1
        
        self.parent_app.glossary_data.update(new)
        added = len(new)
        msg = [f"{c}개의 {t}을(를) 메모리에 {a}했습니다." for c, t, a in [(added, "새 용어", "추가"), (updated, "기존 용어", "업데이트")] if c > 0]
        if not msg: return messagebox.showinfo("알림", "새로 추가/업데이트할 용어가 없습니다.", parent=self)
        messagebox.showinfo("적용 완료", "\n".join(msg) + "\n\n'변경사항 저장 후 닫기'를 눌러 파일에 최종 반영하세요.", parent=self)
        self.s_input.delete('1.0', tk.END)

    def save_and_close(self):
        self.parent_app.save_current_glossary(); self.destroy()

class PromptGeneratorApp:
    def __init__(self, root):
        self.root = root; self.root.title("3단계 번역 프롬프트 생성기")
        w, h = min(850, root.winfo_screenwidth() - 50), min(760, root.winfo_screenheight() - 100)
        self.root.geometry(f"{w}x{h}")
        self.doc_path, self.glossary_path = tk.StringVar(), tk.StringVar()
        self.chunks, self.glossary_data = [], {}
        self.current_chunk_index, self.current_step = 0, 1
        
        settings = load_settings_from_json()
        self.prompt_1_template = settings["prompt1"]
        self.prompt_2_template = settings["prompt2"]
        self.chunk_size = settings["chunk_size"]
        
        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self.root, padding="10"); top.pack(fill="x")
        ttk.Label(top, text="영어 원문 (.docx):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(top, textvariable=self.doc_path, width=50).grid(row=0, column=1, sticky="ew")
        ttk.Button(top, text="파일 선택", command=lambda: self.select_file(self.doc_path, (("Word", "*.docx"), ("All", "*.*")))).grid(row=0, column=2, padx=5)
        ttk.Label(top, text="번역 용어집 (.txt):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(top, textvariable=self.glossary_path).grid(row=1, column=1, sticky="ew")
        ttk.Button(top, text="파일 선택/생성", command=self.setup_glossary_path).grid(row=1, column=2, padx=5)
        action = ttk.Frame(top); action.grid(row=0, column=3, rowspan=2, padx=10)
        ttk.Button(action, text="불러오기", command=self.load_files).pack(fill="x", ipady=4)
        ttk.Button(action, text="설정", command=self.open_settings).pack(fill="x", pady=2)
        top.columnconfigure(1, weight=1)
        
        mid = ttk.Frame(self.root, padding="10"); mid.pack(fill="x")
        ttk.Label(mid, text="[2단계용] 초벌 번역 결과 입력:").pack(anchor="w")
        self.draft_text = scrolledtext.ScrolledText(mid, wrap=tk.WORD, height=8); self.draft_text.pack(fill="x", expand=True, pady=5)
        
        bot = ttk.Frame(self.root, padding="10"); bot.pack(fill="both", expand=True)
        self.status = ttk.Label(bot, text="진행 상태: 대기 중", font=("", 10, "bold")); self.status.pack(anchor="w")
        self.prompt_display = scrolledtext.ScrolledText(bot, wrap=tk.WORD); self.prompt_display.pack(fill="both", expand=True, pady=5)
        
        ctrl = ttk.Frame(bot); ctrl.pack(fill="x", pady=5)
        self.action_btn = ttk.Button(ctrl, text="단계별 진행", command=self.process_action, state="disabled"); self.action_btn.pack(side="left", padx=10, fill="x", expand=True)
        self.copy_btn = ttk.Button(ctrl, text="프롬프트 복사", command=self.copy_prompt, state="disabled"); self.copy_btn.pack(side="left", padx=10)
        self.prev_btn = ttk.Button(ctrl, text="◀ 이전", command=lambda: self.navigate_chunk(-1), state="disabled"); self.prev_btn.pack(side="left", padx=10)
        self.next_btn = ttk.Button(ctrl, text="다음 ▶", command=lambda: self.navigate_chunk(1), state="disabled"); self.next_btn.pack(side="left", padx=10)

    def open_settings(self): PromptSettingsWindow(self)
    def select_file(self, path_var, ftypes):
        if fp := filedialog.askopenfilename(filetypes=ftypes): path_var.set(fp)
    def setup_glossary_path(self):
        if fp := filedialog.askopenfilename(initialfile="Translation glossary.txt", filetypes=(("Text", "*.txt"), ("All", "*.*"))): return self.glossary_path.set(fp)
        if not self.glossary_path.get() and (sp := self.doc_path.get()):
            dfp = os.path.join(os.path.dirname(sp), "Translation glossary.txt")
            if messagebox.askyesno("파일 생성", f"원문과 같은 위치에 새 용어집 파일을 만드시겠습니까?\n\n{dfp}"):
                try: open(dfp, 'w', encoding='utf-8').close(); self.glossary_path.set(dfp); messagebox.showinfo("생성 완료", f"'{os.path.basename(dfp)}' 생성 완료.")
                except Exception as e: messagebox.showerror("생성 실패", f"파일 생성 오류: {e}")

    def load_files(self):
        if not (path := self.doc_path.get()): return messagebox.showwarning("파일 없음", "영어 원문 파일을 선택해주세요.")
        if not self.glossary_path.get(): self.setup_glossary_path()
        if not self.glossary_path.get(): return
        self.chunks = chunk_document_by_word_count(path, self.chunk_size)
        self.glossary_data = load_glossary(self.glossary_path.get())
        if self.chunks:
            self.current_chunk_index, self.current_step = 0, 1; self.update_ui_for_chunk()
            messagebox.showinfo("완료", f"총 {len(self.chunks)}개 청크, {len(self.glossary_data)}개 용어 로드 완료.")
        else: self.reset_state()

    def process_action(self):
        if not self.chunks: return
        chunk = self.chunks[self.current_chunk_index]
        if self.current_step == 1: prompt, self.current_step = self.prompt_1_template.format(english_chunk=chunk), 2
        elif self.current_step == 2:
            if not (draft := self.draft_text.get('1.0', tk.END).strip()): return messagebox.showwarning("입력 필요", "초벌 번역 결과를 입력해주세요.")
            prompt, self.current_step = self.prompt_2_template.format(english_chunk=chunk, korean_draft=draft), 3
        elif self.current_step == 3:
            ReviewWindow(self); self.current_step = 4; return self.update_button_states()
        self.prompt_display.delete('1.0', tk.END); self.prompt_display.insert(tk.END, prompt); self.update_button_states()

    def navigate_chunk(self, direction):
        new_index = self.current_chunk_index + direction
        if 0 <= new_index < len(self.chunks):
            self.current_chunk_index, self.current_step = new_index, 1; self.update_ui_for_chunk()
        else: messagebox.showinfo("문서 끝", "문서의 처음 또는 마지막입니다.")
    
    def update_ui_for_chunk(self):
        self.prompt_display.delete('1.0', tk.END); self.draft_text.delete('1.0', tk.END)
        self.current_step = 1; self.update_button_states()

    def update_button_states(self):
        if not self.chunks: return self.reset_state()
        total, num = len(self.chunks), self.current_chunk_index + 1
        self.copy_btn.config(state="normal" if self.prompt_display.get('1.0', 'end-1c').strip() else "disabled")
        info = {1:("1단계","초벌 번역 프롬프트 생성","normal"), 2:("2단계","개선 번역 프롬프트 생성","normal"), 3:("3단계","번역 검토 및 완료","normal"), 4:("완료","완료됨","disabled")}
        s, t, st = info.get(self.current_step)
        self.status.config(text=f"진행: 청크 {num}/{total} - [{s}]"); self.action_btn.config(text=f"{self.current_step}. {t}", state=st)
        self.prev_btn.config(state="normal" if self.current_chunk_index > 0 else "disabled")
        self.next_btn.config(state="normal" if self.current_chunk_index < total - 1 else "disabled")

    def reset_state(self):
        self.chunks = []
        for btn in [self.action_btn, self.copy_btn, self.prev_btn, self.next_btn]: btn.config(state="disabled")
        self.status.config(text="진행 상태: 대기 중")
        self.prompt_display.delete('1.0', tk.END); self.draft_text.delete('1.0', tk.END)

    def copy_prompt(self):
        if p := self.prompt_display.get('1.0', tk.END).strip():
            self.root.clipboard_clear(); self.root.clipboard_append(p); messagebox.showinfo("복사 완료", "프롬프트가 클립보드에 복사되었습니다.")
        else: messagebox.showwarning("복사 실패", "복사할 내용이 없습니다.")
    
    def save_current_glossary(self):
        if not (path := self.glossary_path.get()): return messagebox.showerror("오류", "용어집 파일 경로가 지정되지 않았습니다.")
        if save_glossary(path, self.glossary_data): messagebox.showinfo("저장 완료", f"'{os.path.basename(path)}' 파일에 용어집을 저장했습니다.")

if __name__ == "__main__":
    root = tk.Tk()
    app = PromptGeneratorApp(root)
    root.mainloop()
