import os
import shutil
import zipfile
import rarfile
import py7zr
import re
from pathlib import Path
import tempfile
import logging
import argparse
import sys
import subprocess

class FolderOrganizer:
    def __init__(self, source_folder, target_folder="정리완료"):
        self.source_folder = Path(source_folder)
        self.target_folder = self.source_folder / target_folder
        self.protected_folders = ["Downloads", "Tempfile", target_folder]
        self.seven_zip = find_7z_executable()
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 목적 폴더 생성
        self.target_folder.mkdir(exist_ok=True)
        
    def is_protected_folder(self, folder_path):
        """보호된 폴더인지 확인"""
        folder_name = folder_path.name
        return folder_name in self.protected_folders
    
    def analyze_archive_content(self, archive_path):
        """압축 파일 내용 분석"""
        try:
            archive_path = Path(archive_path)
            file_list = []
            
            if archive_path.suffix.lower() == '.zip':
                # 1차: 기본 디코딩
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                except Exception:
                    file_list = []

                # 한글 깨짐 추정 시 CP949 메타데이터 재해석 (Py3.10+)
                if self._looks_mojibake(file_list):
                    try:
                        with zipfile.ZipFile(archive_path, 'r', metadata_encoding='cp949') as zip_ref:
                            file_list = zip_ref.namelist()
                    except TypeError:
                        # metadata_encoding 미지원 파이썬 버전
                        pass
            elif archive_path.suffix.lower() == '.rar':
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    file_list = rar_ref.namelist()
            elif archive_path.suffix.lower() == '.7z':
                with py7zr.SevenZipFile(archive_path, mode='r') as sz_ref:
                    file_list = sz_ref.getnames()
            elif archive_path.suffix.lower() == '.zipx':
                # 시도 1: 표준 ZipFile (일부 zipx는 호환됨)
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                except Exception:
                    file_list = []
                # 실패 시: 7z로 목록 추출
                if not file_list and self.seven_zip:
                    file_list = self._seven_zip_list(archive_path)
                    
            return file_list
        except Exception as e:
            self.logger.error(f"압축 파일 분석 실패 {archive_path}: {e}")
            return []

    def analyze_archive_details(self, archive_path):
        """압축 파일 상세 목록 분석: 이름/크기/디렉터리 여부"""
        try:
            archive_path = Path(archive_path)
            details = []

            if archive_path.suffix.lower() == '.zip':
                def collect(zf):
                    local = []
                    for info in zf.infolist():
                        is_dir = info.is_dir() if hasattr(info, 'is_dir') else info.filename.endswith('/')
                        local.append({
                            'name': info.filename,
                            'size': 0 if is_dir else getattr(info, 'file_size', 0),
                            'is_dir': is_dir
                        })
                    return local

                # 1차 기본
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    details = collect(zip_ref)

                # 깨짐 추정 시 CP949 메타데이터 재해석 (가능하면)
                if self._looks_mojibake([d['name'] for d in details]):
                    try:
                        with zipfile.ZipFile(archive_path, 'r', metadata_encoding='cp949') as zip_ref:
                            details = collect(zip_ref)
                    except TypeError:
                        pass
            elif archive_path.suffix.lower() == '.rar':
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    for member in rar_ref.infolist():
                        is_dir = member.isdir()
                        details.append({
                            'name': member.filename,
                            'size': 0 if is_dir else getattr(member, 'file_size', 0),
                            'is_dir': is_dir
                        })
            elif archive_path.suffix.lower() == '.7z':
                with py7zr.SevenZipFile(archive_path, mode='r') as sz_ref:
                    # list()는 멤버의 속성 포함
                    for m in sz_ref.list():
                        name = getattr(m, 'filename', None) or getattr(m, 'name', '')
                        is_dir = getattr(m, 'is_directory', False)
                        size = 0 if is_dir else int(getattr(m, 'uncompressed', 0) or 0)
                        details.append({
                            'name': name,
                            'size': size,
                            'is_dir': is_dir
                        })
            elif archive_path.suffix.lower() == '.zipx':
                # 우선 ZipFile로 시도
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        for info in zip_ref.infolist():
                            is_dir = info.is_dir() if hasattr(info, 'is_dir') else info.filename.endswith('/')
                            details.append({
                                'name': info.filename,
                                'size': 0 if is_dir else getattr(info, 'file_size', 0),
                                'is_dir': is_dir
                            })
                except Exception:
                    details = []
                # 실패/빈 경우 7z로 보강
                if (not details) and self.seven_zip:
                    details = self._seven_zip_list_details(archive_path)

            return details
        except Exception as e:
            self.logger.error(f"압축 파일 상세 분석 실패 {archive_path}: {e}")
            return []
    
    def extract_specific_file(self, archive_path, target_filename, destination):
        """압축 파일에서 특정 파일만 추출"""
        try:
            archive_path = Path(archive_path)
            
            if archive_path.suffix.lower() == '.zip':
                def try_extract(zf):
                    for file_info in zip_ref.filelist:
                        if target_filename in file_info.filename:
                            zf.extract(file_info.filename, destination)
                            # 파일 이름만 유지하고 경로 제거
                            extracted_path = destination / file_info.filename
                            final_path = destination / Path(file_info.filename).name
                            if extracted_path != final_path:
                                extracted_path.rename(final_path)
                            # 생성된 중간 폴더 정리
                            self._cleanup_empty_parents(destination, extracted_path.parent)
                            return True
                    return False

                # 기본 시도
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    if try_extract(zip_ref):
                        return True
                # 깨짐 추정 시 CP949 재시도
                try:
                    with zipfile.ZipFile(archive_path, 'r', metadata_encoding='cp949') as zip_ref:
                        if try_extract(zip_ref):
                            return True
                except TypeError:
                    pass
                            
            elif archive_path.suffix.lower() == '.rar':
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    for member in rar_ref.infolist():
                        if target_filename in member.filename:
                            rar_ref.extract(member, destination)
                            extracted_path = destination / member.filename
                            final_path = destination / Path(member.filename).name
                            if extracted_path != final_path:
                                extracted_path.rename(final_path)
                            self._cleanup_empty_parents(destination, extracted_path.parent)
                            return True
            elif archive_path.suffix.lower() == '.7z':
                # py7zr는 대상 목록 기반 추출을 지원
                with py7zr.SevenZipFile(archive_path, mode='r') as sz_ref:
                    # 정확 매칭 우선, 없으면 부분 매칭 시도
                    names = sz_ref.getnames()
                    exact_matches = [n for n in names if n == target_filename]
                    candidates = exact_matches or [n for n in names if target_filename in n]
                    if candidates:
                        target = candidates[0]
                        sz_ref.extract(targets=[target], path=destination)
                        extracted_path = destination / target
                        final_path = destination / Path(target).name
                        if extracted_path != final_path and extracted_path.exists():
                            extracted_path.rename(final_path)
                        return True
            elif archive_path.suffix.lower() == '.zipx':
                if self.seven_zip:
                    return self._seven_zip_extract_specific(archive_path, target_filename, destination)
                            
        except Exception as e:
            self.logger.error(f"특정 파일 추출 실패 {archive_path}: {e}")
        return False
    
    def extract_archive(self, archive_path, destination):
        """압축 파일 해제"""
        try:
            archive_path = Path(archive_path)
            
            if archive_path.suffix.lower() == '.zip':
                extracted = False
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(destination)
                        extracted = True
                except Exception:
                    extracted = False
                if not extracted:
                    try:
                        with zipfile.ZipFile(archive_path, 'r', metadata_encoding='cp949') as zip_ref:
                            zip_ref.extractall(destination)
                            extracted = True
                    except TypeError:
                        pass
                if not extracted:
                    return False
            elif archive_path.suffix.lower() == '.rar':
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    rar_ref.extractall(destination)
            elif archive_path.suffix.lower() == '.7z':
                with py7zr.SevenZipFile(archive_path, mode='r') as sz_ref:
                    sz_ref.extractall(destination)
            elif archive_path.suffix.lower() == '.zipx':
                # ZipFile 시도 후 실패 시 7z로 추출
                ok = False
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(destination)
                        ok = True
                except Exception:
                    ok = False
                if not ok and self.seven_zip:
                    return self._seven_zip_extract_all(archive_path, destination)
                if not ok:
                    return False
            
            return True
        except Exception as e:
            self.logger.error(f"압축 해제 실패 {archive_path}: {e}")
            return False
    
    def compress_folder(self, folder_path, output_path):
        """폴더를 ZIP으로 압축"""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(folder_path)
                        zip_ref.write(file_path, arcname)
            return True
        except Exception as e:
            self.logger.error(f"폴더 압축 실패 {folder_path}: {e}")
            return False
    
    def determine_archive_processing_method(self, archive_path, folder_name):
        """압축 파일 처리 방법 결정 (일반화된 기준)"""
        # 상세 목록 분석 (이름/크기/디렉토리)
        details = self.analyze_archive_details(archive_path)
        if not details:
            return "move_as_is", None

        names = [d['name'] for d in details]

        def has_sep(name):
            return ('/' in name) or ('\\' in name)

        def top_dir(name):
            return name.split('/')[0] if '/' in name else name.split('\\')[0]

        top_level_files = [d for d in details if not d['is_dir'] and not has_sep(d['name'])]
        top_level_dirs = set(top_dir(d['name']) for d in details if has_sep(d['name']))

        # 텍스트 파일 기반 규칙: 우선 전역적으로 .txt 존재 여부 검사
        txt_files = [d for d in details if not d['is_dir'] and d['name'].lower().endswith('.txt')]
        if len(txt_files) == 1:
            return "extract_single_file", txt_files[0]['name']

        if len(txt_files) >= 2:
            # 가장 큰 텍스트 파일이 나머지보다 압도적으로 크면 그 파일만 추출
            txt_sorted = sorted(txt_files, key=lambda x: x['size'], reverse=True)
            largest = txt_sorted[0]
            second = txt_sorted[1]
            if (largest['size'] >= max(1024 * 1024, 10 * (second['size'] or 1))) or (second['size'] <= 10 * 1024):
                return "extract_single_file", largest['name']

        # 구조 기반 규칙: 최상위에 폴더만 여러 개 있고 파일이 없으면 각 폴더를 개별 압축
        if len(top_level_files) == 0 and len(top_level_dirs) >= 2:
            return "extract_and_recompress_folders", None

        # 단일 파일만 루트에 존재하면 그 파일만 추출
        if len(top_level_files) == 1 and len(top_level_dirs) == 0:
            return "extract_single_file", top_level_files[0]['name']

        # 기본: 모두 해제 (내부의 추가 압축파일은 그대로 유지됨)
        return "extract_all", None
    
    def process_archive_file(self, archive_path, folder_name):
        """압축 파일 처리"""
        method, target_file = self.determine_archive_processing_method(archive_path, folder_name)
        archive_name = Path(archive_path).stem
        
        self.logger.info(f"압축 파일 처리: {archive_path} - 방법: {method}")
        
        if method == "extract_single_file":
            # 루트의 단일 파일만 추출
            ok = self.extract_specific_file(archive_path, target_file, self.target_folder)
            if ok:
                self._cleanup_source_after_processing(Path(archive_path))
            return ok
            
        elif method == "move_as_is":
            # 압축 파일 그대로 이동
            dest_path = self.target_folder / Path(archive_path).name
            shutil.move(str(archive_path), str(dest_path))
            return True
            
        elif method == "extract_all":
            # 새 폴더 만들고 압축 해제
            new_folder = self.target_folder / archive_name
            new_folder.mkdir(exist_ok=True)
            ok = self.extract_archive(archive_path, new_folder)
            if ok:
                self._cleanup_source_after_processing(Path(archive_path))
            return ok

        elif method == "extract_and_recompress_folders":
            # 압축 해제 후 최상위 폴더들을 각각 ZIP으로 재압축
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                if self.extract_archive(archive_path, temp_path):
                    new_folder = self.target_folder / archive_name
                    new_folder.mkdir(exist_ok=True)
                    for item in temp_path.iterdir():
                        if item.is_dir():
                            zip_name = f"{item.name}.zip"
                            zip_path = new_folder / zip_name
                            self.compress_folder(item, zip_path)
                        else:
                            shutil.copy2(item, new_folder)
                    self._cleanup_source_after_processing(Path(archive_path))
                    return True
        
        return False

    @staticmethod
    def _looks_mojibake(names):
        """간단한 한글 깨짐 패턴 감지: 박스문자/선문자 등 포함 여부 체크"""
        if not names:
            return False
        suspicious_chars = set("┌┐└┘├┤┬┴┼─│╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬")
        for n in names:
            if any(ch in n for ch in suspicious_chars):
                return True
        return False

    @staticmethod
    def _cleanup_empty_parents(base_dir: Path, start_dir: Path):
        """start_dir에서 base_dir까지의 빈 폴더를 삭제"""
        try:
            current = Path(start_dir)
            base_dir = Path(base_dir).resolve()
            while current.resolve().is_relative_to(base_dir):
                # base_dir 자체는 삭제하지 않음
                if current.resolve() == base_dir.resolve():
                    break
                if current.exists() and current.is_dir() and not any(current.iterdir()):
                    current.rmdir()
                    current = current.parent
                else:
                    break
        except Exception:
            # 정리 실패는 작업을 막지 않음
            pass

    def _cleanup_source_after_processing(self, archive_path: Path):
        """처리 완료 후 원본 압축 파일과 빈 원본 폴더 정리"""
        try:
            # 원본 압축 파일 제거
            if archive_path.exists():
                archive_path.unlink()
        except Exception:
            pass
    
    def _remove_empty_dirs(self, root: Path):
        """root 하위의 빈 폴더를 재귀적으로 삭제 (보호/목적 폴더 제외)"""
        try:
            root = Path(root)
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                current = Path(dirpath)
                # 목적 폴더 혹은 보호 폴더는 삭제 금지
                if current == self.target_folder:
                    continue
                if self.is_protected_folder(current):
                    continue
                try:
                    if not any(current.iterdir()):
                        self._force_remove_dir(current)
                except Exception:
                    pass
        except Exception:
            pass

    def _force_remove_dir(self, path: Path):
        """Windows에서 잠금 문제를 우회하며 폴더 삭제 (빈 폴더 가정)"""
        try:
            # 파일 속성 Read-only 해제 시도
            try:
                os.chmod(path, 0o700)
            except Exception:
                pass
            # 1차 시도: 빈 폴더 직접 삭제
            path.rmdir()
        except OSError:
            # 혹시 잔여 숨김파일 등이 있다면 강제 재시도
            try:
                for child in path.glob('**/*'):
                    try:
                        os.chmod(child, 0o700)
                    except Exception:
                        pass
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

    # 7-Zip 보조기능들
    def _seven_zip_list(self, archive_path: Path):
        try:
            if not self.seven_zip:
                return []
            cmd = [self.seven_zip, 'l', '-ba', str(archive_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            lines = res.stdout.splitlines()
            files = []
            for line in lines:
                # 7z -ba 리스트 형식: date time attr size compressed name
                parts = line.strip().split()
                if len(parts) >= 6:
                    name = ' '.join(parts[5:])
                    if name not in ['.', '..']:
                        files.append(name)
            return files
        except Exception:
            return []

    def _seven_zip_list_details(self, archive_path: Path):
        try:
            if not self.seven_zip:
                return []
            cmd = [self.seven_zip, 'l', '-slt', str(archive_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            details = []
            current = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith('Path = '):
                    if current:
                        details.append(current)
                        current = {}
                    current['name'] = line[len('Path = '):]
                elif line.startswith('Folder = '):
                    current['is_dir'] = (line[len('Folder = '):].lower() == 'true')
                elif line.startswith('Size = '):
                    try:
                        current['size'] = int(line[len('Size = '):] or '0')
                    except ValueError:
                        current['size'] = 0
            if current:
                details.append(current)
            return details
        except Exception:
            return []

    def _seven_zip_extract_all(self, archive_path: Path, destination: Path):
        try:
            if not self.seven_zip:
                return False
            destination = Path(destination)
            destination.mkdir(exist_ok=True)
            cmd = [self.seven_zip, 'x', '-y', f'-o{destination}', str(archive_path)]
            res = subprocess.run(cmd, capture_output=True)
            return res.returncode == 0
        except Exception:
            return False

    def _seven_zip_extract_specific(self, archive_path: Path, target_filename: str, destination: Path):
        try:
            if not self.seven_zip:
                return False
            destination = Path(destination)
            destination.mkdir(exist_ok=True)
            cmd = [self.seven_zip, 'x', '-y', f'-o{destination}', str(archive_path), f'*{target_filename}*']
            res = subprocess.run(cmd, capture_output=True)
            return res.returncode == 0
        except Exception:
            return False
    
    def process_folder_contents(self, folder_path):
        """폴더 내용 처리"""
        if not folder_path.exists():
            return True
        files = list(folder_path.iterdir())
        regular_files = [f for f in files if f.is_file() and not self.is_archive(f)]
        archive_files = [f for f in files if f.is_file() and self.is_archive(f)]
        
        # 압축 파일이 2개 이상인 경우
        if len(archive_files) >= 2:
            folder_name = folder_path.name
            new_folder = self.target_folder / folder_name
            new_folder.mkdir(exist_ok=True)
            
            for file in files:
                if file.is_file():
                    dest_path = new_folder / file.name
                    shutil.move(str(file), str(dest_path))
            # 정리 후 빈 폴더 재귀 삭제
            self._remove_empty_dirs(folder_path)
            return True
        
        # 압축 파일이 1개인 경우
        elif len(archive_files) == 1:
            archive_file = archive_files[0]
            ok = self.process_archive_file(archive_file, folder_path.name)
            # 남은 항목(파일/폴더)이 있으면 폴더를 만들어 이동
            if not folder_path.exists():
                return ok or True
            remaining_items = [p for p in folder_path.iterdir() if p.exists()]
            remaining_items = [p for p in remaining_items if p.name != archive_file.name]
            if remaining_items:
                new_folder = self.target_folder / folder_path.name
                new_folder.mkdir(exist_ok=True)
                for item in remaining_items:
                    dest_path = new_folder / item.name
                    try:
                        if item.is_file():
                            shutil.move(str(item), str(dest_path))
                        elif item.is_dir():
                            shutil.move(str(item), str(dest_path))
                    except Exception as e:
                        self.logger.error(f"남은 항목 이동 실패 {item}: {e}")
            # 정리 후 빈 폴더 재귀 삭제
            self._remove_empty_dirs(folder_path)
            return ok or True
        
        # 일반 파일만 있는 경우
        else:
            if len(regular_files) <= 3:
                # 3개 이하: 직접 이동
                for file in regular_files:
                    dest_path = self.target_folder / file.name
                    shutil.move(str(file), str(dest_path))
            else:
                # 4개 이상: 새 폴더 생성 후 이동
                folder_name = folder_path.name
                new_folder = self.target_folder / folder_name
                new_folder.mkdir(exist_ok=True)
                
                for file in regular_files:
                    dest_path = new_folder / file.name
                    shutil.move(str(file), str(dest_path))
            return True
    
    def is_archive(self, file_path):
        """압축 파일인지 확인"""
        return file_path.suffix.lower() in ['.zip', '.rar', '.7z', '.zipx']
    
    def organize_folders(self):
        """메인 폴더 정리 함수"""
        self.logger.info(f"폴더 정리 시작: {self.source_folder}")
        
        # 현재 폴더의 서브 폴더들 가져오기
        subfolders = [item for item in self.source_folder.iterdir() 
                     if item.is_dir() and not self.is_protected_folder(item)]
        
        processed_folders = []
        
        for subfolder in subfolders:
            try:
                self.logger.info(f"처리 중인 폴더: {subfolder.name}")
                
                # 폴더 내용 처리
                if self.process_folder_contents(subfolder):
                    processed_folders.append(subfolder)
                    self.logger.info(f"폴더 처리 완료: {subfolder.name}")
                else:
                    self.logger.warning(f"폴더 처리 실패: {subfolder.name}")
                    
            except Exception as e:
                self.logger.error(f"폴더 처리 중 오류 {subfolder.name}: {e}")
        
        # 빈 폴더 삭제 (다시 한 번 확인)
        for folder in processed_folders:
            try:
                if folder.exists() and folder.is_dir() and not any(folder.iterdir()):
                    self._force_remove_dir(folder)
                    self.logger.info(f"빈 폴더 삭제: {folder.name}")
            except Exception as e:
                self.logger.error(f"폴더 삭제 실패 {folder.name}: {e}")
        
        # 전체 트리에서 빈 폴더 최종 정리
        try:
            self._remove_empty_dirs(self.source_folder)
        except Exception:
            pass
        
        self.logger.info("폴더 정리 완료")

def find_unrar_near_executable():
    """실행 파일(또는 스크립트) 근처에 있는 unrar.exe 자동 감지"""
    try:
        # PyInstaller로 빌드된 경우 exe 디렉터리, 스크립트 실행 시에는 파일의 디렉터리
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).resolve().parent
        candidates = [
            base_dir / "unrar.exe",
            base_dir / "UnRAR.exe",
            Path(r"C:\\Program Files\\WinRAR\\UnRAR.exe"),
            Path(r"C:\\Program Files (x86)\\WinRAR\\UnRAR.exe"),
            Path(r"C:\\Program Files\\WinRAR\\UnRAR64.exe"),
            Path(r"C:\\Program Files (x86)\\WinRAR\\UnRAR64.exe"),
        ]
        for cand in candidates:
            if cand.exists():
                rarfile.UNRAR_TOOL = str(cand)
                break
    except Exception:
        pass

def find_7z_executable():
    """7z.exe 자동 탐지 (zipx 등 처리용)"""
    candidates = [
        Path(os.environ.get('ProgramFiles', r'C:\\Program Files')) / '7-Zip' / '7z.exe',
        Path(os.environ.get('ProgramFiles(x86)', r'C:\\Program Files (x86)')) / '7-Zip' / '7z.exe',
        Path('7z.exe'),
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass
    return None

def parse_args():
    parser = argparse.ArgumentParser(description="서브 폴더 자동 정리기")
    parser.add_argument("--source", "-s", default=os.getcwd(), help="정리할 소스 폴더 (기본: 현재 폴더)")
    parser.add_argument("--target", "-t", default="정리완료", help="목적 폴더명 (기본: 정리완료)")
    parser.add_argument("--yes", "-y", action="store_true", help="확인 없이 바로 실행")
    parser.add_argument("--no-pause", action="store_true", help="작업 종료 후 일시정지하지 않음")
    return parser.parse_args()

def main():
    args = parse_args()
    try:
        source_folder = args.source
        if not os.path.exists(source_folder):
            print("폴더가 존재하지 않습니다.")
            return

        target_folder_name = args.target or "정리완료"

        # unrar 자동 감지 설정
        find_unrar_near_executable()

        organizer = FolderOrganizer(source_folder, target_folder_name)

        print("\n=== 폴더 정리 시작 ===")
        print(f"소스 폴더: {source_folder}")
        print(f"목적 폴더: {organizer.target_folder}")
        print(f"보호된 폴더: {', '.join(organizer.protected_folders)}")

        if args.yes:
            organizer.organize_folders()
            print("\n폴더 정리가 완료되었습니다!")
            return

        confirm = input("\n계속 진행하시겠습니까? (y/N): ").strip().lower()
        if confirm == 'y':
            organizer.organize_folders()
            print("\n폴더 정리가 완료되었습니다!")
        else:
            print("작업이 취소되었습니다.")
    except Exception as e:
        logging.exception(f"예기치 못한 오류: {e}")
    finally:
        if not args.no_pause:
            try:
                input("\n종료하려면 Enter 키를 누르세요...")
            except Exception:
                pass

if __name__ == "__main__":
    main()