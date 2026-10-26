// General guidance for the FAQ UI. Replace with approved company policy summaries.
// These are not generated answers or a source of company-specific rules.
export const POLICY_FAQ_CATEGORIES = [
  {
    id: 'leave',
    label: '휴가·근태',
    title: '휴가와 근태',
    description: '휴가 신청부터 근무 기록까지, 자주 찾는 내용을 확인하세요.',
    questions: [
      {
        id: 'leave-request',
        question: '연차는 어떻게 신청하나요?',
        summary:
          '연차 신청 전에는 잔여일수, 신청 기한, 승인 절차를 확인해 주세요. 근무 조건에 따라 적용 기준이 다를 수 있으니 자세한 절차를 질문해 보세요.',
      },
      {
        id: 'leave-carryover',
        question: '사용하지 못한 연차는 이월할 수 있나요?',
        summary:
          '이월 가능 여부와 사용 기한은 적용되는 사내 지침을 확인해야 합니다. 남은 연차와 사용하지 못한 사유를 함께 알려주시면 확인할 내용을 더 구체적으로 질문할 수 있어요.',
      },
      {
        id: 'attendance-correction',
        question: '출퇴근 기록이 누락되었어요. 어떻게 수정하나요?',
        summary:
          '누락된 날짜와 실제 근무 시간, 수정 사유를 먼저 정리해 주세요. 근태 담당자나 사내 시스템에서 필요한 증빙과 수정 절차를 확인해 보세요.',
      },
    ],
  },
  {
    id: 'travel',
    label: '출장·경비',
    title: '출장과 경비',
    description: '출장 준비와 비용 정산에 필요한 내용을 살펴보세요.',
    questions: [
      {
        id: 'travel-request',
        question: '출장을 가기 전에 어떤 절차가 필요한가요?',
        summary:
          '출장 일정과 목적, 예상 비용을 정리하고 사전 승인 여부를 확인해 주세요. 교통·숙박 예약 전에 적용되는 출장 기준도 함께 확인하면 좋아요.',
      },
      {
        id: 'expense-documents',
        question: '출장 경비 정산에 어떤 서류가 필요한가요?',
        summary:
          '지출 내역과 영수증 등 증빙 자료를 정리한 뒤 정산 기한과 제출 경로를 확인해 주세요. 비용 항목에 따라 인정 기준이나 추가 서류가 달라질 수 있어요.',
      },
      {
        id: 'expense-receipt',
        question: '영수증을 분실했을 때는 어떻게 하나요?',
        summary:
          '거래 일시와 금액, 사용 목적을 정리하고 영수증 재발급 가능 여부를 확인해 보세요. 대체 증빙의 인정 여부는 경비 담당자에게 확인이 필요해요.',
      },
    ],
  },
  {
    id: 'benefits',
    label: '복리후생',
    title: '복리후생',
    description: '내게 필요한 복지 제도와 신청 방법을 찾아보세요.',
    questions: [
      {
        id: 'benefits-eligibility',
        question: '제가 신청할 수 있는 복지 혜택은 무엇인가요?',
        summary:
          '복지 제도별로 지원 대상, 신청 기간과 필요한 서류를 확인해 주세요. 확인하고 싶은 혜택을 구체적으로 질문하면 적용 기준을 살펴보기 쉬워요.',
      },
      {
        id: 'benefits-family-event',
        question: '경조사 지원은 어떻게 신청하나요?',
        summary:
          '경조사 유형과 대상 가족, 발생일을 기준으로 지원 대상과 신청 기한을 확인해 주세요. 경조 휴가와 지원금은 각각의 신청 절차를 살펴보는 것이 좋아요.',
      },
      {
        id: 'benefits-health',
        question: '건강검진 지원 기준과 신청 방법이 궁금해요.',
        summary:
          '검진 대상과 예약 기간, 이용 가능한 기관을 먼저 확인해 주세요. 추가 검사나 가족 검진의 지원 여부는 해당 복지 지침에서 별도로 확인이 필요해요.',
      },
    ],
  },
  {
    id: 'general',
    label: '기타',
    title: '기타 업무 안내',
    description: '증명서 발급부터 사무실 이용까지, 일상적인 업무 질문을 모았어요.',
    questions: [
      {
        id: 'general-certificate',
        question: '재직증명서는 어떻게 발급받나요?',
        summary:
          '증명서의 사용 목적과 제출처, 필요한 발급 부수를 정리해 주세요. 사내 신청 경로나 인사 담당자에게 발급 방법과 소요 시간을 확인할 수 있어요.',
      },
      {
        id: 'general-meeting-room',
        question: '회의실은 어떻게 예약하나요?',
        summary:
          '이용 날짜와 시간, 참석 인원과 필요한 장비를 먼저 확인해 주세요. 사내 예약 경로나 총무 담당자를 통해 이용 가능한 회의실과 예약 방법을 확인해 보세요.',
      },
      {
        id: 'general-supplies',
        question: '사무용품이나 업무 장비는 어디에 신청하나요?',
        summary:
          '필요한 품목과 수량, 사용 목적을 정리한 뒤 신청 경로와 승인 절차를 확인해 주세요. 장비의 경우 지급·대여 여부와 준비 기간도 담당자에게 함께 문의하면 좋아요.',
      },
    ],
  },
]
