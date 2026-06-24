"""
Static dataset configuration for generate_datasets.py.

Separated to keep generate_datasets.py under 200 lines.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent

ENTITY_SOURCE_FILES = {
    "visionchat.md",
    "datapulse.md",
    "auth-service.md",
    "hotfix-v121.md",
    "q32024-okr-review.md",
    "engineering-department.md",
}

MONGODB_KEYWORDS = [
    "lương",
    "salary",
    "payroll",
    "doanh thu",
    "revenue",
    "headcount",
    "nhân sự",
    "attendance",
    "chấm công",
    "kpi",
    "okr",
    "bug",
    "ticket",
    "chi phí",
    "infrastructure cost",
    "tuyển dụng",
    "recruitment",
    "sprint",
    "model registry",
    "đi muộn",
    "muộn",
]

KNOWN_ENTITIES = [
    "visionchat",
    "datapulse",
    "auth service",
    "auth-service",
    "hotfix",
    "mlops",
    "saigonbank",
    "nlu",
    "rag engine",
    "bot engine",
    "knowledge base indexer",
    "engineering department",
    "ai research",
    "villm",
    "api gateway",
    "kong",
]

WIKI_DOCS = [
    p
    for p in [
        str(ROOT / "wiki/services/visionchat.md"),
        str(ROOT / "wiki/services/datapulse.md"),
        str(ROOT / "wiki/services/auth-service.md"),
        str(ROOT / "wiki/pipelines/incident-handling-process.md"),
        str(ROOT / "wiki/pipelines/release-process.md"),
        str(ROOT / "wiki/decisions/hotfix-v121.md"),
        str(ROOT / "wiki/decisions/q32024-okr-review.md"),
        str(ROOT / "wiki/person/human-resources-department.md"),
        str(ROOT / "wiki/person/engineering-department.md"),
        str(ROOT / "wiki/concepts/ai-tools-usage-guidelines.md"),
    ]
    if Path(p).exists()
]

MT_SCENARIOS = [
    {
        "scenario": "Nhân viên mới muốn tìm hiểu về auth-service: ngôn ngữ lập trình, framework, port, số replicas, và cơ chế xác thực.",
        "expected_outcome": "Nhân viên nắm được đầy đủ thông tin kỹ thuật của auth-service bao gồm Go/Gin, port 8002, 2 replicas và JWT/OAuth.",
        "user_description": "Nhân viên kỹ thuật mới tại TechVision AI đang tìm hiểu kiến trúc hệ thống.",
    },
    {
        "scenario": "Developer hỏi về API Gateway: công nghệ sử dụng, các chức năng chính, và cách nó kết nối với các service khác.",
        "expected_outcome": "Developer hiểu rõ API Gateway dùng Kong/Nginx, xử lý rate limiting, auth, routing đến các internal services.",
        "user_description": "Senior developer đang thiết kế tích hợp client mới.",
    },
    {
        "scenario": "Product manager muốn hiểu quy trình CI/CD của TechVision: các bước từ commit đến production, công cụ sử dụng.",
        "expected_outcome": "PM nắm được pipeline CI/CD với GitHub Actions, Docker, Kubernetes và quy trình review/deploy.",
        "user_description": "Product manager cần nắm quy trình kỹ thuật để lên kế hoạch release.",
    },
    {
        "scenario": "Nhân viên hỏi về chính sách nghỉ phép: số ngày phép năm, quy trình xin phép, và chính sách WFH.",
        "expected_outcome": "Nhân viên biết rõ chính sách nghỉ phép và WFH của công ty.",
        "user_description": "Nhân viên mới cần tìm hiểu chính sách HR của công ty.",
    },
    {
        "scenario": "Tech lead muốn khám phá mối quan hệ giữa bot-engine và các service liên quan: NLU service, RAG engine, response generator.",
        "expected_outcome": "Tech lead hiểu rõ luồng xử lý của bot-engine và các dependency service của nó.",
        "user_description": "Tech lead đang thiết kế kiến trúc cho tính năng mới.",
    },
    {
        "scenario": "Architect hỏi về knowledge-base-indexer: pipeline xử lý, các component liên quan, và luồng dữ liệu đến vector database.",
        "expected_outcome": "Architect nắm được toàn bộ knowledge base indexing pipeline và dependency graph.",
        "user_description": "Solution architect đang đánh giá khả năng mở rộng hệ thống.",
    },
    {
        "scenario": "HR muốn biết danh sách nhân viên đi muộn trong tháng 10/2024 và số lần đi muộn của từng người.",
        "expected_outcome": "HR có danh sách đầy đủ nhân viên đi muộn với thông tin chi tiết từ attendance_october_2024.",
        "user_description": "Nhân viên HR đang làm báo cáo chấm công tháng.",
    },
    {
        "scenario": "Finance muốn xem tổng chi phí infrastructure tháng 9/2024 theo từng provider và category dịch vụ.",
        "expected_outcome": "Finance có breakdown chi phí cloud infrastructure theo AWS/GCP, chia theo Compute/Database/Network v.v.",
        "user_description": "Finance analyst đang lập báo cáo chi phí vận hành.",
    },
    {
        "scenario": "COO hỏi về tình hình revenue tháng 6-9/2024: tổng MRR, số khách hàng mới, churn rate và gross margin.",
        "expected_outcome": "COO có cái nhìn tổng quan về business metrics 4 tháng gần nhất từ revenue_2024.",
        "user_description": "COO cần dữ liệu cho báo cáo board meeting.",
    },
    {
        "scenario": "Trưởng phòng kỹ thuật muốn xem danh sách bug priority Critical đang còn mở và assignee của từng bug.",
        "expected_outcome": "Trưởng phòng có danh sách bug Critical chưa resolved với assignee để theo dõi.",
        "user_description": "Engineering manager đang review tình trạng quality của sprint hiện tại.",
    },
    {
        "scenario": "New hire hỏi: NLU service là gì, nó liên kết với những service nào, và hiện có bao nhiêu sprint ticket liên quan đến NLU.",
        "expected_outcome": "New hire hiểu NLU service (wiki), các service liên quan (graph), và tình trạng sprint tickets (mongodb).",
        "user_description": "Kỹ sư mới vừa join team AI/ML muốn nắm codebase.",
    },
    {
        "scenario": "Manager muốn tuyển thêm Python developer: hiện pipeline tuyển dụng có bao nhiêu ứng viên đang active, vị trí nào đang tuyển nhiều nhất.",
        "expected_outcome": "Manager nắm được số ứng viên active, top positions đang tuyển từ recruitment_pipeline.",
        "user_description": "Engineering manager đang lên kế hoạch headcount Q4.",
    },
    {
        "scenario": "Product manager hỏi về DataPulse: tiến độ hiện tại bao nhiêu phần trăm, ngân sách tổng và đã chi bao nhiêu, deadline dự kiến.",
        "expected_outcome": "PM biết DataPulse đạt 32% progress, budget 1800M VNĐ, đã chi 620M, và deadline kế hoạch.",
        "user_description": "Product manager cần cập nhật tình trạng dự án cho stakeholder.",
    },
    {
        "scenario": "Business analyst hỏi về VisionChat: accuracy hiện tại, MRR, số khách hàng đang dùng, và các tính năng nổi bật.",
        "expected_outcome": "Analyst nắm VisionChat đạt 92.3% accuracy, MRR 0.53B, 10 clients và các tính năng chính.",
        "user_description": "Business analyst chuẩn bị tài liệu pitching cho khách hàng tiềm năng.",
    },
    {
        "scenario": "Scrum master hỏi chi tiết về hotfix v1.2.1: thời điểm xảy ra sự cố, thời gian khắc phục, số phiên bị ảnh hưởng, và nguyên nhân gốc rễ.",
        "expected_outcome": "Scrum master biết hotfix v1.2.1 xảy ra 02/09/2024, giải quyết trong 2h31m, ảnh hưởng 420 sessions và root cause.",
        "user_description": "Scrum master cần viết báo cáo retrospective về incident.",
    },
    {
        "scenario": "Giám đốc hỏi về kết quả OKR Q3/2024: doanh thu thực tế so với mục tiêu, số hợp đồng ký được, và OKR nào đạt/không đạt.",
        "expected_outcome": "Giám đốc nắm Q3 2024 đạt 7.2B/8B VNĐ, 4/5 hợp đồng, và chi tiết từng OKR.",
        "user_description": "CEO đang chuẩn bị board presentation Q3.",
    },
    {
        "scenario": "Scrum master muốn xem sprint velocity 3 sprint gần nhất: story points committed vs completed, và sprint nào có completion rate thấp nhất.",
        "expected_outcome": "Scrum master có dữ liệu velocity trend và sprint có completion rate thấp nhất để cải thiện.",
        "user_description": "Scrum master đang chuẩn bị retrospective và capacity planning.",
    },
    {
        "scenario": "Customer success muốn xem điểm NPS và CSAT của các khách hàng Enterprise trong Q3/2024, sắp xếp theo score thấp nhất.",
        "expected_outcome": "CS team có danh sách khách hàng Enterprise với NPS/CSAT thấp để ưu tiên follow-up.",
        "user_description": "Customer success manager đang lên kế hoạch retention cho khách hàng Enterprise.",
    },
    {
        "scenario": "Developer muốn biết VisionChat phụ thuộc vào những service nào, service nào phụ thuộc ngược lại vào VisionChat.",
        "expected_outcome": "Developer hiểu full dependency graph của VisionChat: upstream dependencies và downstream consumers.",
        "user_description": "Developer cần assess impact trước khi deploy breaking change cho VisionChat.",
    },
    {
        "scenario": "DevOps muốn hiểu quy trình xử lý incident P1: các bước theo pipeline, SLA cụ thể, và hiện đang có bao nhiêu incident P1 open trong tháng này.",
        "expected_outcome": "DevOps nắm quy trình P1 (wiki/pipeline), SLA 5 phút, và số lượng P1 đang open (mongodb).",
        "user_description": "DevOps engineer vừa được phân công on-call duty.",
    },
]
