# 티링크 AI 영업사례 에디터

현장사진과 제품 자료를 읽고 잠재 기업 고객이 궁금해할 질문에 답하는 홍보 콘텐츠를 만듭니다. 기업 블로그, 인스타그램 카드뉴스, 기업 소개 이메일을 지원합니다.

## 실행 예시

1. ChatGPT에서 ‘티링크 AI 영업사례 에디터’를 호출합니다. 제출 폴더를 사용하는 환경에서는 루트의 SKILL.md를 실행 지침으로 사용합니다.
2. [현장사진](inputs/images/field-photo-01.jpg)과 [티링크 비즈레코딩 제품제안서](inputs/티링크비즈레코딩_제품제안서.pptx)를 함께 첨부합니다. 새 사례를 만들 때는 해당 현장사진과 제품 자료로 교체할 수 있습니다.
3. “이 자료로 티링크를 처음 접하는 기업 고객에게 보여 줄 인스타그램 카드뉴스를 만들어 줘.”라고 요청합니다. ‘기업 블로그’ 또는 ‘기업 소개 이메일’로 바꾸면 그 매체에 맞게 결과를 만듭니다.

사진에서 확인되는 장비와 제품 자료의 설명을 대조합니다. 스탠드형은 독립 본체를 둘 환경, 렉거치형은 기존 랙 활용, 미러링스위치허브는 추가하는 허브의 크기를 중심으로 안내합니다. 공개 자료로 확인된 내용과 활용 예시는 구분합니다.

## 결과물 보기

| 매체 | 완성본 | 함께 제공하는 파일 |
|---|---|---|
| 기업 블로그 | [사진을 포함한 PDF](outputs/tlink-blog.pdf) | [편집 원고](outputs/tlink-blog.md), [HTML](outputs/tlink-blog.html), [근거 검수표](outputs/check-report.md) |
| 인스타그램 카드뉴스 | [1장](outputs/instagram/card-01.png) · [2장](outputs/instagram/card-02.png) · [3장](outputs/instagram/card-03.png) · [4장](outputs/instagram/card-04.png) · [5장](outputs/instagram/card-05.png) | [게시문·대체텍스트](outputs/instagram/caption.txt), [전체 미리보기 HTML](outputs/instagram/cardnews.html), [근거 검수표](outputs/instagram/check.md) |
| 기업 소개 이메일 | [메일 초안 EML](outputs/email/intro.eml) | [미리보기 HTML](outputs/email/intro.html), [복사용 텍스트](outputs/email/intro.txt), [근거 검수표](outputs/email/check.md) |

HTML은 내려받아 브라우저에서 열고 EML은 메일 앱에서 엽니다. 시연에 사용한 자료와 출처는 [입력 설명](inputs/input.md)과 [제품 근거표](references/product-facts.md)에 있습니다.

## 예시 파일 다시 출력하기

폴더 전체를 내려받아 압축을 풉니다. Python 3 환경에서 저장소의 최상위 폴더를 열고 아래 명령을 실행합니다. 명령은 준비된 예시 원고와 채널별 문구를 읽어 지정한 폴더에 파일을 씁니다. 새로운 홍보 문구를 만들 때는 위의 스킬 실행 절차를 사용합니다.

```sh
python -m pip install Pillow PyMuPDF reportlab
python render_blog.py outputs/tlink-blog.md --brand 티링크 --label "기업 도입 가이드"
python render_channels.py instagram inputs/channel-brief.json --out outputs
python render_channels.py email inputs/channel-brief.json --out outputs
```
