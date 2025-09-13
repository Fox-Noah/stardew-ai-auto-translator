
import requests
import concurrent.futures
import threading
from typing import List, Dict, Optional, Callable


class OllamaManager:
    
    def __init__(self, main_app=None, base_url: str = 'http://localhost:11434', model: str = None):
        self.base_url = base_url
        self.model = model
        self.translator = OllamaTranslator(base_url=base_url, model=model, main_app=main_app)
        self.main_app = main_app
    
    def check_server_status(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=0.5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=0.5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception:
            return []
    
    def set_model(self, model: str):
        self.model = model
        self.translator.model = model
    
    def translate_single_text(self, text: str, target_lang: str) -> str:
        return self.translator.translate_single_text(text, target_lang)
    
    def translate_batch_async(self, texts: List[str], target_lang: str, batch_size: int = 5,
                            progress_callback: Optional[Callable] = None,
                            stop_check: Optional[Callable] = None,
                            result_callback: Optional[Callable] = None) -> List[str]:
        return self.translator.translate_batch_async(
            texts, target_lang, batch_size, progress_callback, stop_check, result_callback
        )
    
    def refresh_models(self):
        def refresh():
            try:
                if self.main_app:
                    self.main_app.log_message("正在刷新模型列表...")
                if self.check_server_status():
                    models = self.get_available_models()
                    if self.main_app:
                        self.main_app.available_models = models
                        self.main_app.root.after(0, lambda: self.main_app._update_models_ui(models))
                        if models:
                            self.model = models[0]
                        self.main_app.log_message("模型列表刷新成功")
                    else:
                        print("模型列表刷新成功")
                else:
                    if self.main_app:
                        self.main_app.log_message("Ollama服务未运行", "ERROR")
                    else:
                        print("Ollama服务未运行")
            except Exception as e:
                if self.main_app:
                    self.main_app.log_message(f"刷新模型列表失败: {str(e)}", "ERROR")
                else:
                    print(f"刷新模型列表失败: {str(e)}")
        
        threading.Thread(target=refresh, daemon=True).start()


class OllamaTranslator:
    
    def __init__(self, base_url: str = 'http://localhost:11434', model: str = None, main_app=None):
        self.model = model
        self.base_url = base_url
        self.main_app = main_app
    
    def translate_single_text(self, text: str, target_lang: str) -> str:
        try:
            lang_config = {
                'zh': {
                    'name': '中文',
                    'examples': [
                        ("Level {{level}} shield found!", "发现等级{{level}}护盾！"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "模组由{{author}}制作 - 依赖项：{{parents}}"),
                        ("Great sword with level {{level}}", "等级{{level}}大剑"),
                        ("Farm Quarry", "农场采石场"),
                        ("Elliot's Cabin", "艾利欧特的小屋"),
                        ("Iridium Quarry", "铱矿采石场"),
                        ("Beer, mead, and pale ale are worth 50% more.", "啤酒、蜂蜜酒和淡啤酒的价值提高50%。"),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "阿比盖尔和山姆去看塞巴斯蒂安，而潘妮在哈维诊所附近教文森特和贾斯，玛鲁在那里和她的父亲德米特里厄斯一起工作。"),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "亚历克斯帮助海莉拍照，而莉亚雕刻雕塑，艾利欧特写诗，卡洛琳和乔迪与艾芙琳和乔治一起准备晚餐。")
                    ]
                },
                'default': {
                    'name': 'English',
                    'examples': [
                        ("Level {{level}} shield found!", "Level {{level}} shield found!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod created by {{author}} - Requirements: {{parents}}"),
                        ("Great sword with level {{level}}", "Great sword with level {{level}}"),
                        ("Farm Quarry", "Farm Quarry"),
                        ("Elliot's Cabin", "Elliott's Cabin"),
                        ("Iridium Quarry", "Iridium Quarry"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Beer, mead, and pale ale are worth 50% more."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.")
                    ]
                },
                'ja': {
                    'name': '日本語',
                    'examples': [
                        ("Level {{level}} shield found!", "レベル{{level}}の盾を発見！"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "{{author}}によって作成されたMod - 必要条件：{{parents}}"),
                        ("Great sword with level {{level}}", "レベル{{level}}の大剣"),
                        ("Farm Quarry", "農場の採石場"),
                        ("Elliot's Cabin", "エリオットの小屋"),
                        ("Iridium Quarry", "イリジウム採石場"),
                        ("Beer, mead, and pale ale are worth 50% more.", "ビール、ミード、ペールエールの価値が50%向上します。"),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "アビゲイルとサムはセバスチャンに会いに行き、ペニーはハーヴィーの診療所近くでヴィンセントとジャスに教えていました。そこではマルが父親のデメトリウスと一緒に働いています。"),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "アレックスはヘイリーの写真撮影を手伝い、リアは彫刻を彫り、エリオットは詩を書いていました。その間、キャロラインとジョディはエヴリンとジョージと一緒に夕食を準備していました。")
                    ]
                },
                'ko': {
                    'name': '한국어',
                    'examples': [
                        ("Level {{level}} shield found!", "레벨 {{level}} 방패 발견!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "{{author}}가 제작한 모드 - 요구사항: {{parents}}"),
                        ("Great sword with level {{level}}", "레벨 {{level}} 대검"),
                        ("Farm Quarry", "농장 채석장"),
                        ("Elliot's Cabin", "엘리엇의 오두막"),
                        ("Iridium Quarry", "이리듐 채석장"),
                        ("Beer, mead, and pale ale are worth 50% more.", "맥주, 벌꿀술, 페일 에일의 가치가 50% 증가합니다."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "애비게일과 샘은 세바스찬을 보러 갔고, 페니는 하비의 진료소 근처에서 빈센트와 재스를 가르치고 있었습니다. 그곳에서 마루는 아버지 데메트리우스와 함께 일하고 있었습니다."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "알렉스는 헤일리의 사진 촬영을 도왔고, 리아는 조각을 조각하고 엘리엇은 시를 썼으며, 캐롤라인과 조디는 에블린과 조지와 함께 저녁을 준비했습니다.")
                    ]
                },
                'fr': {
                    'name': 'Français',
                    'examples': [
                        ("Level {{level}} shield found!", "Bouclier de niveau {{level}} trouvé !"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod créé par {{author}} - Prérequis : {{parents}}"),
                        ("Great sword with level {{level}}", "Grande épée de niveau {{level}}"),
                        ("Farm Quarry", "Carrière de la ferme"),
                        ("Elliot's Cabin", "Cabane d'Elliott"),
                        ("Iridium Quarry", "Carrière d'iridium"),
                        ("Beer, mead, and pale ale are worth 50% more.", "La bière, l'hydromel et la bière blonde valent 50% de plus."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail et Sam sont allés voir Sebastian, tandis que Penny enseignait à Vincent et Jas près de la clinique d'Harvey où Maru travaille avec son père Demetrius."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex a aidé Haley à prendre des photos tandis que Leah sculptait et qu'Elliott écrivait des poèmes, pendant que Caroline et Jodi préparaient le dîner avec Evelyn et George.")
                    ]
                },
                'de': {
                    'name': 'Deutsch',
                    'examples': [
                        ("Level {{level}} shield found!", "Schild der Stufe {{level}} gefunden!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod erstellt von {{author}} - Voraussetzungen: {{parents}}"),
                        ("Great sword with level {{level}}", "Großes Schwert der Stufe {{level}}"),
                        ("Farm Quarry", "Farm-Steinbruch"),
                        ("Elliot's Cabin", "Elliotts Hütte"),
                        ("Iridium Quarry", "Iridium-Steinbruch"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Bier, Met und helles Bier sind 50% mehr wert."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail und Sam gingen zu Sebastian, während Penny Vincent und Jas in der Nähe von Harveys Klinik unterrichtete, wo Maru mit ihrem Vater Demetrius arbeitet."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex half Haley beim Fotografieren, während Leah Skulpturen schnitzte und Elliott Gedichte schrieb, als Caroline und Jodi das Abendessen mit Evelyn und George zubereiteten.")
                    ]
                },
                'es': {
                    'name': 'Español',
                    'examples': [
                        ("Level {{level}} shield found!", "¡Escudo de nivel {{level}} encontrado!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod creado por {{author}} - Requisitos: {{parents}}"),
                        ("Great sword with level {{level}}", "Gran espada de nivel {{level}}"),
                        ("Farm Quarry", "Cantera de la granja"),
                        ("Elliot's Cabin", "Cabaña de Elliott"),
                        ("Iridium Quarry", "Cantera de iridio"),
                        ("Beer, mead, and pale ale are worth 50% more.", "La cerveza, el hidromiel y la cerveza pálida valen 50% más."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail y Sam fueron a ver a Sebastian, mientras Penny enseñaba a Vincent y Jas cerca de la clínica de Harvey donde Maru trabaja con su padre Demetrius."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex ayudó a Haley a tomar fotos mientras Leah tallaba esculturas y Elliott escribía poemas, mientras Caroline y Jodi preparaban la cena con Evelyn y George.")
                    ]
                },
                'ru': {
                    'name': 'Русский',
                    'examples': [
                        ("Level {{level}} shield found!", "Найден щит {{level}} уровня!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Мод создан {{author}} - Требования: {{parents}}"),
                        ("Great sword with level {{level}}", "Большой меч {{level}} уровня"),
                        ("Farm Quarry", "Карьер фермы"),
                        ("Elliot's Cabin", "Хижина Эллиота"),
                        ("Iridium Quarry", "Иридиевый карьер"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Пиво, медовуха и светлый эль стоят на 50% больше."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Эбигейл и Сэм пошли к Себастьяну, пока Пенни учила Винсента и Джас возле клиники Харви, где Мару работает со своим отцом Деметриусом."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Алекс помогал Хейли фотографировать, пока Лия вырезала скульптуры, а Эллиот писал стихи, когда Кэролайн и Джоди готовили ужин с Эвелин и Джорджем.")
                    ]
                },
                'pt-BR': {
                    'name': 'Português (BR)',
                    'examples': [
                        ("Level {{level}} shield found!", "Escudo nível {{level}} encontrado!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod criado por {{author}} - Requisitos: {{parents}}"),
                        ("Great sword with level {{level}}", "Grande espada nível {{level}}"),
                        ("Farm Quarry", "Pedreira da fazenda"),
                        ("Elliot's Cabin", "Cabana do Elliott"),
                        ("Iridium Quarry", "Pedreira de irídio"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Cerveja, hidromel e cerveja clara valem 50% a mais."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail e Sam foram ver Sebastian, enquanto Penny ensinava Vincent e Jas perto da clínica do Harvey onde Maru trabalha com seu pai Demetrius."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex ajudou Haley a tirar fotos enquanto Leah esculpia e Elliott escrevia poemas, enquanto Caroline e Jodi preparavam o jantar com Evelyn e George.")
                    ]
                },
                'it': {
                    'name': 'Italiano',
                    'examples': [
                        ("Level {{level}} shield found!", "Scudo di livello {{level}} trovato!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "Mod creata da {{author}} - Requisiti: {{parents}}"),
                        ("Great sword with level {{level}}", "Grande spada di livello {{level}}"),
                        ("Farm Quarry", "Cava della fattoria"),
                        ("Elliot's Cabin", "Capanna di Elliott"),
                        ("Iridium Quarry", "Cava di iridio"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Birra, idromele e birra chiara valgono il 50% in più."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail e Sam andarono a trovare Sebastian, mentre Penny insegnava a Vincent e Jas vicino alla clinica di Harvey dove Maru lavora con suo padre Demetrius."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex aiutò Haley a scattare foto mentre Leah scolpiva e Elliott scriveva poesie, mentre Caroline e Jodi preparavano la cena con Evelyn e George.")
                    ]
                },
                'tr': {
                    'name': 'Türkçe',
                    'examples': [
                        ("Level {{level}} shield found!", "Seviye {{level}} kalkan bulundu!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "{{author}} tarafından oluşturulan mod - Gereksinimler: {{parents}}"),
                        ("Great sword with level {{level}}", "Seviye {{level}} büyük kılıç"),
                        ("Farm Quarry", "Çiftlik taş ocağı"),
                        ("Elliot's Cabin", "Elliott'un kulübesi"),
                        ("Iridium Quarry", "İridyum taş ocağı"),
                        ("Beer, mead, and pale ale are worth 50% more.", "Bira, bal şarabı ve açık bira %50 daha değerli."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail ve Sam Sebastian'ı görmeye gitti, Penny ise Harvey'nin kliniği yakınında Vincent ve Jas'a ders veriyordu, Maru'nun babası Demetrius ile çalıştığı yerde."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex, Haley'nin fotoğraf çekmesine yardım etti, Leah heykel oyarken Elliott şiir yazıyordu, Caroline ve Jodi ise Evelyn ve George ile akşam yemeği hazırlıyordu.")
                    ]
                },
                'hu': {
                    'name': 'Magyar',
                    'examples': [
                        ("Level {{level}} shield found!", "{{level}}. szintű pajzs találva!"),
                        ("Mod created by {{author}} - Requirements: {{parents}}", "{{author}} által készített mod - Követelmények: {{parents}}"),
                        ("Great sword with level {{level}}", "{{level}}. szintű nagy kard"),
                        ("Farm Quarry", "Farm kőbánya"),
                        ("Elliot's Cabin", "Elliott kunyhója"),
                        ("Iridium Quarry", "Irídium kőbánya"),
                        ("Beer, mead, and pale ale are worth 50% more.", "A sör, mézsör és világos sör 50%-kal többet ér."),
                        ("Abigail and Sam went to see Sebastian, while Penny was teaching Vincent and Jas near Harvey's clinic where Maru works with her father Demetrius.", "Abigail és Sam elmentek Sebastianhoz, míg Penny Vincent-et és Jas-t tanította Harvey klinikája közelében, ahol Maru az apjával, Demetriusszal dolgozik."),
                        ("Alex helped Haley take photos while Leah carved sculptures and Elliott wrote poems, as Caroline and Jodi prepared dinner with Evelyn and George.", "Alex segített Haley-nek fotózni, míg Leah szobrokat faragott és Elliott verseket írt, Caroline és Jodi pedig Evelyn-nel és George-dzsal készítették a vacsorát.")
                    ]
                }
            }
            
            current_lang = lang_config.get(target_lang, lang_config['zh'])
            target_lang_name = current_lang['name']
            fake_examples = current_lang['examples']
            
            user_prompt = f"你怎么还是把变量名内容翻译了? 请重新理解并将以下星露谷物语代码文本翻译成{target_lang_name}，不允许翻译任何花括号内的变量名避免编译错误, 人名和名词等都必须完全翻译,要求符合官方本地化名称, 只返回翻译结果，不需要解释："
            
            fake_history = []
            for original, translation in fake_examples:
                fake_history.extend([
                    {"role": "user", "content": f"{user_prompt} {original}"},
                    {"role": "assistant", "content": translation}
                ])
            
            fake_history.append({
                "role": "user",
                "content": f"{user_prompt} {text}"
            })
            
            base_url = self.base_url
            if self.main_app and hasattr(self.main_app, 'ollama_base_url'):
                base_url = self.main_app.ollama_base_url
            
            model = self.model
            if self.main_app and hasattr(self.main_app, 'ollama_model'):
                model = self.main_app.ollama_model
            
            response = requests.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": fake_history,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                translated_text = result.get('message', {}).get('content', '').strip()
                return translated_text if translated_text else text
            else:
                return text
                
        except Exception as e:
            return text
    
    def translate_batch_async(self, texts: List[str], target_lang: str, batch_size: int,
                            progress_callback: Optional[Callable] = None,
                            stop_check: Optional[Callable] = None,
                            result_callback: Optional[Callable] = None) -> List[str]:
        results = [None] * len(texts)
        total = len(texts)
        completed = 0
        lock = threading.Lock()
        
        max_workers = min(batch_size, len(texts))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self.translate_single_text, text, target_lang): i
                for i, text in enumerate(texts)
            }
            
            for future in concurrent.futures.as_completed(future_to_index):
                try:
                    index = future_to_index[future]
                    translated_text = future.result()
                    results[index] = translated_text if translated_text else texts[index]
                    
                    with lock:
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total, f"已完成 {completed}/{total} 条翻译")
                        
                        if result_callback:
                            result_callback(index, texts[index], results[index])
                            
                except Exception as e:
                    index = future_to_index[future]
                    results[index] = texts[index]
                    with lock:
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total, f"已完成 {completed}/{total} 条翻译（第{index+1}条失败）")
                
                if stop_check and stop_check():
                    for f in future_to_index:
                        if not f.done():
                            f.cancel()
                    break
        
        for i, result in enumerate(results):
            if result is None:
                results[i] = texts[i]
        
        return results