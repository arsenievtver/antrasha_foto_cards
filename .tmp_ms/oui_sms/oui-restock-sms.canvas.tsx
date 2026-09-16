import {
  BarChart,
  Callout,
  Grid,
  H1,
  H2,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

type Buyer = {
  name: string;
  phone: string;
  last: string;
  qty: number;
  checks: number;
  recentAny: boolean;
};

const BUYERS: Buyer[] = [
  { name: "Соберова Наталья Сергеевна", phone: "+79106460286", last: "21.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Червяков Руслан Юнадиевич", phone: "+79206820936", last: "22.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Айкерекова Елена Сергеевна", phone: "+79190594632", last: "24.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Ермолаева Нина Михайловна", phone: "+79161719871", last: "24.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Махсон Мария Олеговна", phone: "+79051285553", last: "24.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Буримова Ирина Владимировна", phone: "+79201541223", last: "27.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Косарева Наталья Александровна", phone: "+79065503333", last: "29.08.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Марина", phone: "+79190657787", last: "30.08.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Добуш Любовь Михайловна", phone: "+79166739874", last: "13.09.2025", qty: 2, checks: 2, recentAny: false },
  { name: "Иванова Надежда Викторовна", phone: "+79201744120", last: "13.09.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Анисимова Ольга Андреевна", phone: "+79051263838", last: "16.09.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Попова Яна Евгеньевна", phone: "+79038062761", last: "18.09.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Дремачева Светлана Геннадьевна", phone: "+79201560079", last: "25.09.2025", qty: 2, checks: 2, recentAny: false },
  { name: "Акопян Оксана Мамедовна", phone: "+79056069090", last: "10.10.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Григорян Елена Юрьевна", phone: "+79101785400", last: "10.10.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Корнилова Лариса Николаевна", phone: "+79157057700", last: "17.10.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Лепехина Анна Александровна", phone: "+79105325959", last: "18.10.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Агафонов Александр Викторович", phone: "+79036306685", last: "22.10.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Будылко Наталья Павловна", phone: "+79036945932", last: "09.11.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Касенова Галина Викторовна", phone: "+79040046663", last: "16.11.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Шевченко Ольга Васильевна", phone: "+79632227126", last: "18.11.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Пожидаев Иван Юрьевич", phone: "+79201911001", last: "24.11.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Комарова Ольга Евгеньевна", phone: "+79106473264", last: "29.11.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Кукарских Яна Андреевна", phone: "+79201536638", last: "29.11.2025", qty: 1, checks: 1, recentAny: true },
  { name: "Григорьева Рамиля Римовна", phone: "+79106483693", last: "30.11.2025", qty: 5, checks: 2, recentAny: false },
  { name: "Тараканова Анжелика Владимировна", phone: "+79038008481", last: "30.11.2025", qty: 4, checks: 2, recentAny: false },
  { name: "Миронов Вячеслав Викторович", phone: "+79157463333", last: "06.12.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Поволокина Ирина Михайловна", phone: "+79106487711", last: "10.12.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Мерц Елена Васильевна", phone: "+79105344073", last: "19.12.2025", qty: 3, checks: 1, recentAny: true },
  { name: "Земина Татьяна Юрьевна", phone: "+79036309745", last: "20.12.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Лукин Сергей Константинович", phone: "+79201810000", last: "20.12.2025", qty: 2, checks: 1, recentAny: false },
  { name: "Сухова Наталья Константиновна", phone: "+79610155888", last: "20.12.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Забелин Николай Николаевич", phone: "+79607080011", last: "21.12.2025", qty: 2, checks: 1, recentAny: true },
  { name: "Мазур Наталья Рудольфовна", phone: "+79106486317", last: "21.12.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Ль Хажи Елена Абдул-Латифовна", phone: "+79105326593", last: "26.12.2025", qty: 1, checks: 1, recentAny: false },
  { name: "Гордеев Роман Николаевич", phone: "+79157055783", last: "05.01.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Прохорова Алена Валерьевна", phone: "+79201559265", last: "07.01.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Пуздырева Татьяна Васильевна", phone: "+79162058042", last: "11.01.2026", qty: 7, checks: 4, recentAny: false },
  { name: "Зайфт Ольга Борисовна", phone: "+79157429917", last: "04.02.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Бильсон Евгения Юрьевна", phone: "+79636998181", last: "07.02.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Сабельникова Екатерина Федоровна", phone: "+79106408082", last: "07.02.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Базаров Дмитрий Александрович", phone: "+79157044909", last: "21.02.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Евгеньев Григорий Евгеньевич", phone: "+79040089441", last: "21.02.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Татьяна Петрова", phone: "+79109303322", last: "22.02.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Петраков Валентин", phone: "+79106470787", last: "06.03.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Колосов Николай Геннадьевич", phone: "+79106472979", last: "08.03.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Шрам Ирина Евгеньевна", phone: "+79051313239", last: "08.03.2026", qty: 2, checks: 2, recentAny: true },
  { name: "Сидорова Анна Витальевна", phone: "+79106492295", last: "10.03.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Ковалевская Юлия Валентиновна", phone: "+79175680119", last: "11.03.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Большакова Надежда Алексеевна", phone: "+79157000049", last: "15.04.2026", qty: 1, checks: 2, recentAny: false },
  { name: "Камарова Ирина Валентиновна", phone: "+79065497134", last: "17.04.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Петрова Галина", phone: "+79109393960", last: "17.04.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Харитонова Ирина Александровна", phone: "+79854766165", last: "18.04.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Юля Красюк", phone: "+79157138213", last: "20.04.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Петрова Елена Викторовна", phone: "+79109305527", last: "21.04.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Шпагина Любовь Владимировна", phone: "+79190508491", last: "21.04.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Оганесян Тамара Раченовна", phone: "+79038053177", last: "24.04.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Базлова Алена Михайловна", phone: "+79806403003", last: "26.04.2026", qty: 3, checks: 2, recentAny: false },
  { name: "Просвирова Любовь", phone: "+79066532676", last: "26.04.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Абросова Светлана Владимировна", phone: "+79201503615", last: "30.04.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Шевцова Екатерина Викторовна", phone: "+79206863374", last: "01.05.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Осокина Ирина Валерьевна", phone: "+79301701254", last: "03.05.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Ахмедов Хусейн Эминевич", phone: "+79036304588", last: "06.05.2026", qty: 2, checks: 2, recentAny: true },
  { name: "Нечаева Ирина Владимировна", phone: "+79106472586", last: "06.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Румянцева Марина Викторовна", phone: "+79301708220", last: "11.05.2026", qty: 5, checks: 1, recentAny: false },
  { name: "Соловьева Ирина Викторовна", phone: "+79201672786", last: "12.05.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Губенко Анна Николаевна", phone: "+79201559255", last: "21.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Охотникова Алеся Александровна", phone: "+79301616592", last: "22.05.2026", qty: 4, checks: 2, recentAny: false },
  { name: "Микаленко Светлана Анатольевна", phone: "+79036957348", last: "23.05.2026", qty: 6, checks: 3, recentAny: true },
  { name: "Инюхин Александр", phone: "+79040053556", last: "24.05.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Кострова Людмила Викторовна", phone: "+79051274194", last: "25.05.2026", qty: 3, checks: 3, recentAny: false },
  { name: "Курдюкова Людмила Николаевна", phone: "+79105328623", last: "27.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Мосина Светлана Алексеевна", phone: "+79030335925", last: "27.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Матвеева Татьяна Юрьевна", phone: "+79106403417", last: "29.05.2026", qty: 2, checks: 1, recentAny: true },
  { name: "Спивак Яна Александровна", phone: "+79038029960", last: "29.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Жукова Екатерина Сергеевна", phone: "+79038037171", last: "30.05.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Фролова Елена Алексеевна", phone: "+79108465795", last: "30.05.2026", qty: 7, checks: 5, recentAny: false },
  { name: "Галина", phone: "+79201609052", last: "31.05.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Конышев Вадим Альбертович", phone: "+79038056677", last: "31.05.2026", qty: 8, checks: 1, recentAny: false },
  { name: "Шнейвайс Вячеслав Абелевич", phone: "+79607020149", last: "31.05.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Сульман Виктория Юрьевна", phone: "+79051262299", last: "02.06.2026", qty: 3, checks: 2, recentAny: false },
  { name: "Лидовская Светлана Олеговна", phone: "+79164631069", last: "08.06.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Габеркорн Анна Валерьевна", phone: "+79647915555", last: "19.06.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Разумова Марина Васильевна", phone: "+79109380757", last: "23.06.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Манюк Марина Александровна", phone: "+79056075131", last: "29.06.2026", qty: 5, checks: 3, recentAny: false },
  { name: "Самойлова Жанна Эдуардовна", phone: "+79036305474", last: "08.07.2026", qty: 1, checks: 1, recentAny: true },
  { name: "Шабельная Ирина Владимировна", phone: "+79056058811", last: "08.07.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Иванова Ирина Игоревна", phone: "+79190642940", last: "13.07.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Вопилова Марина Александровна", phone: "+79206978744", last: "17.07.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Гамова Ирина Петровна", phone: "+79106403608", last: "18.07.2026", qty: 2, checks: 2, recentAny: false },
  { name: "Павлова Ольга Олеговна", phone: "+79108459895", last: "20.07.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Борисова Любовь Борисовна", phone: "+79190528223", last: "23.07.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Чаталян Лариса Муксуловна", phone: "+79030332654", last: "24.07.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Степанова Ирина Валерьевна", phone: "+79036310859", last: "28.07.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Богатырев Роман Александрович", phone: "+79106475823", last: "31.07.2026", qty: 2, checks: 1, recentAny: false },
  { name: "Петрова Татьяна Николаевна", phone: "+79108471763", last: "31.07.2026", qty: 3, checks: 2, recentAny: true },
  { name: "Иванова Светлана Владимировна", phone: "+79157474920", last: "01.08.2026", qty: 5, checks: 3, recentAny: false },
  { name: "Рогозин Сергей Николаевич", phone: "+79108300028", last: "04.08.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Юзепчук Любовь Юрьевна", phone: "+79106404900", last: "04.08.2026", qty: 1, checks: 1, recentAny: false },
  { name: "Гурьева Вера Николаевна", phone: "+79038015269", last: "08.08.2026", qty: 1, checks: 1, recentAny: false }
];

const HIST_CATEGORIES = ["авг 25", "сен 25", "окт 25", "ноя 25", "дек 25", "янв 26", "фев 26", "мар 26", "апр 26", "май 26", "июн 26", "июл 26", "авг 26"];
const HIST_VALUES = [8, 5, 5, 8, 9, 3, 6, 5, 11, 20, 5, 11, 4];

export default function OuiRestockSms() {
  const recentAny = BUYERS.filter((b) => b.recentAny).length;
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>Рассылка OUI — новая поставка</H1>
        <Text tone="secondary">
          Покупатели марки OUI за 10.08.2025–10.08.2026. Последняя покупка OUI не
          позже 10.08.2026 (минимум месяц назад). Источник: МойСклад, розничные
          чеки и отгрузки.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value={String(BUYERS.length)} label="номеров в рассылке" />
        <Stat value="108" label="купили OUI в окне" tone="info" />
        <Stat value="13" label="отсеяны: OUI за последний месяц" />
        <Stat value="181" label="вещей OUI у списка" tone="success" />
      </Grid>

      <Callout tone="info" title="Как собран список">
        Взяты все продажи товаров поставщика OUI за 13 месяцев. Оставлены те, у
        кого последняя покупка OUI попала в окно 10.08.2025–10.08.2026. Юрлица,
        «Отказался» и покупатели без телефона не входят. {recentAny} человек из
        списка покупали в магазине что-то другое после 10.08.2026 — в таблице
        помечены.
      </Callout>

      <Stack gap={8}>
        <H2>Когда в последний раз брали OUI</H2>
        <Text tone="secondary" size="small">
          Число человек в рассылке по месяцу последней покупки OUI. Источник:
          МойСклад · 10.08.2025–10.08.2026
        </Text>
        <BarChart
          categories={HIST_CATEGORIES}
          series={[{ name: "Покупатели OUI", data: HIST_VALUES }]}
          height={220}
        />
      </Stack>

      <Stack gap={8}>
        <H2>Телефоны для сообщения</H2>
        <Text tone="secondary" size="small">
          100 уникальных номеров. Файлы: Downloads/OUI_рассылка_телефоны.csv и
          .txt
        </Text>
        <Table
          headers={["Телефон", "Покупатель", "Последняя OUI", "Штук", "Ещё покупал месяц"]}
          columnAlign={["left", "left", "left", "right", "left"]}
          striped
          stickyHeader
          rows={BUYERS.map((b) => [
            b.phone,
            b.name,
            b.last,
            String(b.qty),
            b.recentAny ? "да" : "",
          ])}
          rowTone={BUYERS.map((b) => (b.recentAny ? "warning" : undefined))}
        />
      </Stack>
    </Stack>
  );
}
