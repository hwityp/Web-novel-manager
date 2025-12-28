import os

# 현재 폴더의 모든 파일 이름을 list.txt로 저장
try:
    # 현재 폴더의 파일 목록 가져오기 (본 스크립트 파일 제외)
    current_script = os.path.basename(__file__)
    files = []
    for item in os.listdir("."):
        if os.path.isfile(item) and item != current_script:
            files.append(item)
    
    # 파일 이름 정렬
    files.sort()
    
    # list.txt 파일로 저장
    with open("list.txt", "w", encoding="utf-8") as f:
        for file_name in files:
            f.write(file_name + "\n")
    
    print(f"파일 목록이 'list.txt'에 저장되었습니다.")
    print(f"총 {len(files)}개의 파일이 발견되었습니다.")

except Exception as e:
    print(f"오류가 발생했습니다: {e}")

# 프로그램 종료 전 대기
input("\n아무 키나 눌러서 종료하세요...")