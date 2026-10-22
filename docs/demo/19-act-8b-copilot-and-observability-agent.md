# Act 8B. Ask in your own words – Azure Copilot and the Observability Agent

Act 8B covers minutes 78–93 of the storyline (15 minutes; 17 with the optional scene 5). Its goal is to show that anyone on the team – even a beginner – can ask questions about the estate in plain English, get a first answer in seconds, **see the query behind the answer**, and then **check it against evidence**. The rule of this act fits in one sentence: **"AI proposes, evidence disposes."** Before you start, complete the one-time checklist in section 8B.1 (about 10 minutes): a working Azure Copilot, a network that allows its connections, the prompt cards and answer key of [Appendix F](26-appendices.md), and the recorded data still inside its 30-day retention. The act visits three places in Azure: the Portal with Azure Copilot, the Logs page with the Observability Agent, and an alert page with its Investigate button.

> **Say this:** "Until now we asked our questions in KQL, a query language, and not everybody speaks it. Now watch what happens when we ask in our own words. And watch for one thing: the AI **shows its work**, so we can check it."

## 8B.0 What you will do in this act

| **Scene** | **What you do** | **Where** | **Min.** | **What it proves** |
|---|---|---|---|---|
| 1 | Ask for the Arc servers in plain English | Azure Portal → Copilot | 3 | Anyone can query the inventory. You read the query it wrote. |
| 2 | Ask Copilot to **write KQL**, run it, find and fix a mistake | Portal → Log Analytics → Logs, plus Copilot | 5 | AI writes the first draft, **you check it**. The most valuable scene. |
| 3 | Chat with the workspace | Logs → Observability agent | 2 | The agent shows every query it runs. Its answers match the data. |
| 4 | Investigate the recorded alert | Alert page → Investigate | 5 | A first-pass investigation in about 4 minutes, graded against an answer key. |
| 5 (optional) | Ask the Troubleshooting Agent about the host disk | Portal → virtual machine → Copilot | (2) | A guided, consent-based check, and honest limits. |

Total: **15 minutes** (17 with the optional scene 5). Scene 4 includes about 4 minutes of waiting, which you fill with the talk track in the box of that scene.

## 8B.1 Before you start (10 minutes, once)

> **Where to run it:** **Azure Portal** (browser) and **Windows PowerShell** on the Operator PC. Both are only used to **read**.

- **Open a tab** on the resource group page of the lab (search for `rg-hyperv-arc-monitor-demo` in the top search box). Sign in with the **lab account**. If Microsoft shows "Pick an account", choose your own lab account only.

- **Check that Azure Copilot works for you.** Click the **Copilot** button at the top of the Portal (next to the search box). A pane opens on the right. If you see an "unauthorized" message, a Global Administrator of the tenant must allow you: Portal → search **Azure Copilot admin center** → **Settings → Access management**.

- **Check the network.** Azure Copilot needs WebSocket connections to `https://directline.botframework.com`. On a guest Wi-Fi or a restricted network this is sometimes blocked. Test it before the session.

- **Print or open [Appendix F](26-appendices.md)** (prompt cards and answer key). AI answers are different every time. The answer key is what **you** trust.

- **Learn the never-click list:** **Create Issue**, **Apply / Fix**, **Deploy**, **Run command**, **Delete**. The agents may offer these buttons. In this demo we never press them.

- **Understand the cost.** At the time of writing, Azure Copilot and the Troubleshooting Agent are included at no extra charge and the **Observability Agent** is billed by use (Azure Agent Credits); check the current Azure documentation before you present. Scene 3 is small. Scene 4 (a deep investigation) is the larger item. Run Scene 4 **once**.

- **Check the shelf life of the recorded data.** The recorded scenes live in logs and alerts that are kept **30 days**. When the recording is older than 30 days, the recorded prompts in this act return "no results". Appendix F has "last 24 hours" versions that always work.

- **Prepare the Alert details page for Scene 4.** Scene 4 starts on the **Alert details** page of the recorded alert `hv-cluster-contention-high` (it fired at 07:46 UTC on the recording day): the page that carries the **Investigate** button. Open it once before the session and keep it in its own browser tab or as a saved link. The older alert page that Act 6 opens does not have an **Investigate** button.

- **Fill in the placeholders of the prompt cards.** The prompts of Scenes 2, 4 and 5 contain placeholders in angle brackets. Replace them with the values of **your** recording before you type a prompt. The last column shows the values of the lab's reference recording. All placeholders of this guide are listed in [About this guide](00-about-this-guide.md).

| **Placeholder** | **Meaning** | **Reference recording** |
|---|---|---|
| `<TEST_DATE>` | The day of the recorded tests, written as day, month name and year | The recording day (the day that other acts call `<INCIDENT_DATE>`) |
| `<TEST_START_LT>` / `<TEST_END_LT>` | Start and end of the recorded CPU test in local time (LT, UTC+7), as `HH:MM` | `11:15` / `11:50` |
| `<TEST_START_UTC>` / `<TEST_END_UTC>` | The same two moments in UTC, in ISO 8601 form `YYYY-MM-DDTHH:MM:SSZ` | `04:15:00` / `04:50:00` UTC on the recording day |
| `<ALERT_FIRED_UTC>` | When the real alert fired, for example `HH:MM UTC on D Month YYYY` | `07:46` UTC on the recording day |
| `<SLOW_START_LT>` / `<SLOW_END_LT>` | Approximate start and end of the recorded storage slowdown in local time (LT, UTC+7) | `11:44` / `11:52` |
| `<INCIDENT_DATE>` | The recording day as `YYYY-MM-DD`, used in the PowerShell blocks | The recording day |

> **Beginner tip:** **Never use Copilot's full-screen mode in a demo.** Its left menu lists your recent chats from other topics. Use the narrow pane on the right, as described in the steps below.

> **Beginner tip:** AI answers normally follow the **language of your question**, but a long request can occasionally produce a reply in another language. If you want English for a beginner, add the words **"Answer in English."** to the request.

## 8B.2 Meet Azure Copilot – where it lives

> **Where to run it:** **Azure Portal**, any page. We start on the resource group page.

> **Do this:** Open the resource group page (search for `rg-hyperv-arc-monitor-demo`). At the top of the Portal, next to the search box, click the **Copilot** button. A pane opens on the right. Read the three **suggested prompts**. They say "**this resource group**", which proves that Copilot knows which page you are on.

Azure Copilot opened on the resource group page shows these parts in reading order:

- **(1)** The **Copilot** button in the Portal header.

- **(2)** The **message box**. Type your question here and press **Enter**.

- **(3)** **Suggested prompts** for the page you are on.

- **(4)** The page you are on is Copilot's **context** – but see the warning in Scene 1: it does not always obey it.

Now look at the list of helpers. Click the **small arrow** next to the **New chat** button. The helper menu shows these parts in reading order:

- **(1)** The **arrow** next to "New chat".

- **(2)** The **Agents** – Troubleshooting, Deployment, Optimization, Migration, Resiliency.

- **(3)** **Copilot**: the general helper. This is the one we use first.

**Three different AI helpers – a table to remember:**

| **Helper** | **Where you start it** | **What it is good for** | **Cost (at the time of writing)** |
|---|---|---|---|
| **Azure Copilot** | Copilot button in the Portal header | Questions about Azure in plain English; writes Resource Graph and KQL queries; explains things. | Included |
| **Troubleshooting Agent** (one of the Copilot agents) | Copilot → New chat arrow → Troubleshooting | Guided checks of a VM, disk, AKS. It asks you to choose the resource and the time. | Included |
| **Observability Agent** | Inside **Azure Monitor**: the **Observability agent** button in Logs, or **Investigate** on an alert | Questions about your logs and metrics. Deep investigation of an alert across layers. | Usage-based (Azure Agent Credits) |

> **Be honest:** "The Observability Agent is **not** in the Copilot agent menu. You start it from Azure Monitor – from Logs or from an alert. That is why this act visits three places."

## 8B.3 Scene 1 – "What do we have?" in plain English (3 minutes)

> **Say this:** "In Act 1 we looked at the Azure Arc list. Let me ask for the same thing in a normal sentence."

> **Where to run it:** **Azure Portal**, resource group page, **Copilot** pane (as described in 8B.2).

### Step A – the sentence a beginner would type

> **Do this:** Click the message box and type: `List the Azure Arc-enabled servers in this resource group with their name, location and connection status.` Press **Enter** and wait about 30 seconds.

> **If something goes wrong:** **In the reference run Copilot ignored the words "this resource group".** The query it wrote had **no resource-group filter**, so it listed Arc servers from the **whole subscription** (more machines than the lab's six, of which it showed 5). In a shared subscription that would show unrelated servers on the projector. **Do not run Step A on stage in a shared subscription.** Teach the lesson instead (below) and go to Step B.

> **Beginner tip:** **Habit 1: name the resource group in the sentence. Habit 2: always read the query.** These two habits make Copilot safe to use.

### Step B – name the resource group

> **Do this:** Click **New chat**. Type: `List the Azure Arc-enabled servers in resource group rg-hyperv-arc-monitor-demo only, with name, location and connection status.` Press **Enter**. Wait about 30 seconds. Scroll the pane to the top. **Read the query that Copilot wrote** (described below). Then scroll down and read the answer.

The top of Copilot's reply shows these parts in reading order:

- **(1)** **Your sentence.**

- **(2)** The **ARG Query** box: the query Copilot wrote. ARG means Azure Resource Graph, the Azure inventory database.

- **(3)** This line is the **resource-group filter**. It is what Step A was missing.

- **(4)** The **Run** button. It opens the query in Resource Graph Explorer.

**Read the query in simple words** (you can say this aloud):

| **Line** | **What it says in simple words** |
|---|---|
| `resources` | Start from the table that lists every Azure resource. |
| `\| where type =~ 'microsoft.hybridcompute/machines'` | Keep only Azure Arc-enabled servers. |
| `\| where resourceGroup =~ 'rg-hyperv-arc-monitor-demo'` | Keep only this resource group. |
| `\| project name, location, status = properties.status` | Show three columns: name, location and connection status. |

Copilot's answer in the chat shows these parts in reading order:

- **(1)** The query (its last lines) is still visible above the answer.

- **(2)** The **answer table**: five rows, all "Connected".

- **(3)** The note "**These are the first 5 results**" with a link to Resource Graph Explorer.

> **Be honest:** "Copilot showed **five** of our **six** machines. It says so itself: 'the first 5 results'. The chat answer is a preview. The complete list is one click away."

> **Do this:** Click the **Run** button in the **ARG Query** box (or the link **Azure Resource Graph Explorer**). Wait about 10 seconds. The Resource Graph Explorer opens with the query already filled in and run. Read the bottom line of the result: it must say **Showing 1 – 6 of 6 results**. If you cannot see the rows, drag the horizontal handle (the three dots) between the editor and the results upward.

Resource Graph Explorer shows these parts in reading order:

- **(1)** The **Run** button (the query already ran by itself).

- **(2)** The **result table**: six Arc servers. Five in the primary region, **SQL2019-GUEST** in `southeastasia` – the same as Act 1.

- **(3)** **Showing 1 – 6 of 6 results** – the proof that the chat answer was a preview.

> **What you should see:** Six rows, all "Connected", exactly the six machines of Act 1. HV-HOST-01, RHEL94-GUEST, SQL2019-GUEST, WIN2019-GUEST, WIN2022-GUEST, WIN2025-GUEST-01.

### Verify with PowerShell (optional, 1 minute)

> **Where to run it:** **Operator PC → Windows PowerShell** (not Cloud Shell). Use the variables from Act 0.

**Run the same query that Copilot wrote**

```powershell
$q = "resources | where type =~ 'microsoft.hybridcompute/machines' | where resourceGroup =~ 'rg-hyperv-arc-monitor-demo' | project name, location, status = properties.status"
az graph query -q $q --subscriptions $SUB --first 100 --query "data" -o table
```

> **What you should see:** A table with the same six machines. (The first time, Azure CLI may offer to install the "resource-graph" extension. Answer **Y**.)

> **Beginner tip:** The part `--query "data"` tells Azure CLI to print the rows. Without it you only see a count.

> **Good to know:** You **ask a question**, see the **query** that answers it, and can save it. The point is not the AI. The point is that the AI **hands you the query** instead of hiding it.

> **Say this:** "Two habits. First: we named the resource group. Second: we read the query. If you do those two things, you can trust this tool – and every answer is checkable in ten seconds."

## 8B.4 Scene 2 – Copilot writes the KQL for me (5 minutes)

> **Say this:** "Our Workbook and dashboards ask questions in KQL. Writing KQL is a skill. Let us see whether Copilot can write the first draft – and let us **check its homework**."

This is the most valuable scene in the act. It has **five small steps**: an easy request that works, a harder request that **fails in a useful way**, a discovery query, the corrected query, and an "explain this query" request.

> **Where to run it:** **Azure Portal** → search box → type `law-arc-monitor-lab` → open the **Log Analytics workspace** → left menu **Logs**. Keep the **Copilot** pane open on the right.

> **Do this:** If a **Welcome** window or the **Queries hub** appears, close it with its **Close** button. At the top right of the query area, open the drop-down **Simple mode** and choose **KQL mode**. (We need a text editor to paste a query.) Click the **Copilot** button in the Portal header. In the pane click **New chat**.

> **Be honest:** "Copilot is **not automatically attached to this workspace**. Its suggested prompts are generic. So in every request we **name the workspace**, `law-arc-monitor-lab`."

### 2a – An easy request that works

> **Do this:** In the Copilot message box type: `Write a KQL query for the Log Analytics workspace law-arc-monitor-lab that shows which computers sent a heartbeat in the last 30 minutes and how many minutes ago their last heartbeat was.` Press **Enter**. Wait up to **60 seconds**. (Copilot first looks the workspace up in Resource Graph, then writes the query. This is normal.) In the answer, click the small **Copy** icon in the top right corner of the grey **kusto** box. Click in the **query editor** on the left, press **Ctrl+A** (select all), then **Ctrl+V** (paste), then click **Run**.

Copilot's answer shows these parts in reading order:

- **(1)** Copilot's first step: a lookup of the workspace in Resource Graph. It only shows the query here. It is normal.

- **(2)** The **KQL answer** (the grey box).

- **(3)** The **Copy** icon.

- **(4)** The **working-mode** drop-down: **Simple mode** now, **KQL mode** next.

After you paste and run the query, the page shows these parts in reading order (six computers, 0 to 1 minute ago):

- **(1)** **KQL mode** is on.

- **(2)** The **pasted query** (five lines).

- **(3)** The **Run** button.

- **(4)** The **result**: six computers and `MinutesAgo` 0 or 1. All machines are reporting.

- **(5)** Copilot's answer – the source of the pasted text.

> **What you should see:** Six computers (HV-HOST-01, RHEL94-GUEST, SQL2019-GUEST, WIN2019-GUEST, WIN2022-GUEST, WIN2025-GUEST-01), each 0 or 1 minute since the last heartbeat. This is the same idea as the heartbeat query of Act 8, but we did not type it.

> **Say this:** "Copilot wrote a correct query in a few seconds. Heartbeat is a well-known table. Now let us give it something harder – something that depends on **our** data."

### 2b – A harder request: the host CPU during our test (local time)

> **Do this:** In the Copilot pane click **New chat**. Type: `In the Log Analytics workspace law-arc-monitor-lab, write a KQL query that shows the Hyper-V host CPU usage of HV-HOST-01 every 5 minutes on <TEST_DATE> between <TEST_START_LT> and <TEST_END_LT> local time (UTC+7).` (Replace the placeholders with the values of your recording; see the table in 8B.1.) Press **Enter**, wait, then read the query. **Do not copy it yet.** First look at line 3 and line 4.

Copilot's draft for the host CPU shows these parts in reading order. Read before you paste:

- **(1)** Copilot can reply in a language other than English, especially to a long request. The words of the query are the same in any language; add "Answer in English." if you want English.

- **(2)** The **KQL**.

- **(3)** Line 3 chooses the counter: ObjectName `Processor`, CounterName `% Processor Time`.

- **(4)** Line 4 filters the time. Copilot **converted local time (UTC+7) to UTC correctly**: 11:15–11:50 LT became 04:15Z–04:50Z.

> **Say this:** "Two things to notice. The time conversion is right, which is a common mistake for people. But the counter name – 'Processor' – is something Copilot **guessed**. Let us run it and see."

> **Do this:** Paste the query into the editor (click the Copy icon, click the editor, **Ctrl+A**, **Ctrl+V**) and click **Run**.

The result shows no error – and no results:

- **(1)** The counter line. It names an object that **does not exist** for this host.

- **(2)** The message "**No results found from the specified time range**".

- **(3)** **Run**.

> **Be honest:** "The query ran **without any error** and returned **nothing**. That does not mean the host was idle. It means the query asked for a counter that does not exist here. **Empty is not zero.** An AI draft is a first draft."

### 2c – Ask Copilot to find the right counter

> **Do this:** In the Copilot pane (same chat) type: `That query returned no results. Write a KQL query that lists the distinct ObjectName and CounterName values in the Perf table for computer HV-HOST-01 in the last 7 days, with the number of samples. Answer in English.` Copy the new query, paste it into the editor (**Ctrl+A**, **Ctrl+V**) and click **Run**. Read the result list. In the reference recording it had about 75 rows (with only the shipped host rule attached it has about 30). Look at the **ObjectName** column: you will see many names that start with **Hyper-V**.

A discovery query lists the counters that really exist:

- **(1)** Your follow-up sentence. You told Copilot what happened.

- **(2)** Copilot's **discovery query**: "which counters exist for this computer?"

- **(3)** The result: one row for each counter (**75 rows** in the reference recording).

- **(4)** The **Hyper-V Hypervisor Logical Processor** counters. These are the host-level CPU counters used by the Workbook.

> **Beginner tip:** This is the **most useful habit** with any AI tool: when an answer is empty, **do not argue with the AI – ask it to list what exists**. Then choose with your eyes.

### 2d – Give Copilot the exact names and ask for a corrected query

> **Do this:** In the Copilot pane type: `Rewrite the host CPU query for HV-HOST-01 using ObjectName "Hyper-V Hypervisor Logical Processor", CounterName "% Total Run Time" and InstanceName "_Total". Average every 5 minutes for <TEST_DATE> between <TEST_START_LT> and <TEST_END_LT> local time (UTC+7). Answer in English.` Copy the new query, paste it into the editor and click **Run**. If a small grey list of suggestions appears in the editor, press **Esc**.

The corrected query matches the evidence:

- **(1)** Your sentence with the **exact names** (the top of the chat is scrolled out of view).

- **(2)** Copilot's **corrected KQL**.

- **(3)** The **result**: seven 5-minute averages.

- **(4)** The **plateau**: 94.7, 97.7 and 88.0 percent between 04:25 and 04:40 UTC, which is **11:25–11:40 LT**.

> **What you should see:** Seven rows (times are UTC; recorded lab result). 13.4, 24.6, **94.7, 97.7, 88.0**, 12.5, 9.0 percent. The plateau is the same shape as the Workbook chart in Act 3.

> **Say this:** "Now the AI's query agrees with the Workbook we showed earlier: host CPU near 100 percent for about fifteen minutes, then back to normal. **The AI proposed. The evidence disposed.**"

**A trap you can reveal (optional, 1 minute; it needs the `Processor Information` counters on the host, which the shipped host rule does not collect, so skip it if your host lacks them).** Copilot's first guess was `Processor`. The nearest real counter has a similar name: `Processor Information / % Processor Time`. If you had used it, the same window would have looked **idle**:

| **5-minute bin (UTC)** | **Hyper-V counter – the hypervisor's view** | **`Processor Information` – only the host's own partition** |
|---|---|---|
| 04:15 | 13.4 % | 2.0 % |
| 04:25 | **94.7 %** | 7.2 % |
| 04:30 | **97.7 %** | 1.1 % |
| 04:35 | **88.0 %** | 1.3 % |
| 04:45 | 9.0 % | 0.8 % |

> **Be honest:** "Two counters, both 'CPU', opposite stories: 98 percent and 1 percent. The **second** one only sees the host's own small partition, not the virtual machines. Only checking the result against evidence, and knowing which counter measures what, tells you which is right. That is why we show you the query."

### 2e – "Explain this query" for the beginner

> **Do this:** In the Copilot pane click **New chat**. Paste a query and ask: `Explain this KQL query to a beginner in simple English, line by line, in at most 6 short bullet points:` followed by the Act 8 heartbeat query (Appendix F, card 2e).

Copilot's explanation shows these parts in reading order:

- **(1)** The explanation: Heartbeat table, time filter, resource-group filter, last seen, age in minutes, order. **All six are correct.**

- **(2)** Suggested next questions.

> **Say this:** "Copilot also works as a teacher. Somebody who has never seen KQL can ask 'what does this line do?' and get a correct answer in seconds. The query stays on the screen, so they can check it."

### Verify with PowerShell (optional, 1 minute)

> **Where to run it:** **Operator PC → Windows PowerShell**. Variables `$SUB` and `$RG` come from Act 0.

**The corrected query from the command line** (replace `<TEST_START_UTC>` and `<TEST_END_UTC>` with the ISO 8601 UTC timestamps of your recording; see the table in 8B.1)

```powershell
$WS  = az monitor log-analytics workspace show --subscription $SUB -g $RG -n law-arc-monitor-lab --query customerId -o tsv
$KQL = "Perf | where Computer == 'HV-HOST-01' | where ObjectName == 'Hyper-V Hypervisor Logical Processor' and CounterName == '% Total Run Time' and InstanceName == '_Total' | where TimeGenerated between (datetime(<TEST_START_UTC>) .. datetime(<TEST_END_UTC>)) | summarize avg_CounterValue = avg(CounterValue) by bin(TimeGenerated, 5m) | order by TimeGenerated asc"
az monitor log-analytics query --workspace $WS --analytics-query $KQL --query "[].{Time:TimeGenerated, AvgCpuPercent:avg_CounterValue}" -o table
```

> **What you should see:** A table of seven rows: 13.36, 24.56, 94.65, 97.67, 88.00, 12.48, 9.03. The same numbers as in the Portal.

> **Beginner tip:** **Why single quotes?** Copilot often writes text in double quotes. In Windows PowerShell, double quotes inside a long command can break Azure CLI. KQL accepts both kinds, so we change every `"` to `'` before running a Copilot query in PowerShell.

### How to write a good request – seven rules

| **Rule** | **Example** |
|---|---|
| 1. Name the **workspace** or resource group. | "…in the Log Analytics workspace law-arc-monitor-lab…" |
| 2. Name the **table** or the thing you want. | "…from the Perf table…", "…heartbeat…" |
| 3. Give the **time range and the time zone**. | "…between 11:15 and 11:50 local time (UTC+7) on the recording day…" or "…in the last 24 hours" |
| 4. Say what to **calculate**. | "average every 5 minutes", "count by computer" |
| 5. If you know the exact name, **write it**. | ObjectName `Hyper-V Hypervisor Logical Processor` |
| 6. Say the **language** you want. | "Answer in English." |
| 7. **One question at a time.** Then refine. | "Now add a filter for HV-HOST-01.", "Explain line 3." |

> **Good to know:** What we show here is **transparency**: the question, the query and the data belong to you, and anybody can check the query. With any assistant, the test is: **can I see exactly what it asked, and can I rerun it myself?**

> **If something goes wrong:** **If Copilot returns something different from this guide** (it will, AI is not deterministic): do not worry. Use the **saved queries in Appendix F**. Paste them in the editor. The evidence is the same. If Copilot is slow or unavailable, say so calmly and switch to the saved queries.

## 8B.5 Scene 3 – Chat with the workspace (2 minutes)

> **Say this:** "Now a different helper: the **Observability Agent**. It lives inside Azure Monitor, next to your logs. We ask a business question: **where does our monitoring data – and our monitoring cost – come from?**"

> **Where to run it:** **Azure Portal** → `law-arc-monitor-lab` → **Logs** (as in Scene 2). The button is in the **toolbar above the query area**.

> **Do this:** Close the Copilot pane with its **X** (top right of the pane). In the toolbar of the Logs page click **Observability agent** (the first button, left of **Save**). A panel opens on the right with the title **Observability Agent – Temporary chat**. Read the greeting. Notice the three buttons at the bottom: **Resource breakdown**, **Ingestion volume**, **Investigate a resource**.

The Observability Agent panel greets you and offers three starting points. It shows these parts in reading order:

- **(1)** The agent's name and "**Temporary chat**": nothing is saved unless you decide so.

- **(2)** The greeting: "I'm connected to **1 Log Analytics workspace** resource". It even noticed the last query we ran and offers to use it.

- **(3)** The **suggestion buttons**. Clicking one only **fills the box** – it does not send.

- **(4)** The text that the button put in the box.

- **(5)** The blue **Send** arrow. **You must click it.**

> **Do this:** Click **Ingestion volume**. The text `Which tables and resources used the most ingestion volume in the last 24 hours?` appears in the box. Click the blue **Send** arrow at the right end of the box. Wait about **one minute**. While it works you can see each step and each **query** it runs. When it finishes, the steps fold into one line, "**Reasoned for 1.13 minutes**". Click that line to unfold them again.

The answer shows which tables produce the most data, in these parts:

- **(1)** "**Reasoned for 1.13 minutes**". This is the line that unfolds the steps and the queries.

- **(2)** The **table**: Perf 227 MB, Heartbeat 5 MB, Event 3 MB and two custom tables below 1 MB, for the last 24 hours.

- **(3)** The agent's **honest limit**: "I couldn't break ingestion down to emitting resources from Usage data".

- **(4)** The agent's **next suggestions**.

> **What you should see:** **Perf is the top table by a wide margin** (recorded lab result: about 227 MB in 24 hours, about 96 percent of the data). Your numbers will be a little different on another day. The order of the tables will not change.

> **Say this:** "Perf – the performance counters we collect – is almost all of our data. That is a cost conversation in one minute: if we want to reduce monitoring cost, we look at Perf first. And look at the last bullet: the agent told us what it **could not** do. That is a good sign."

> **Do this:** Click the suggestion **Break down Perf by Computer**, then click **Send**. Wait about **25 seconds**.

The drill-down shows which computer sends the most Perf data, in these parts:

- **(1)** The agent states its **method**: it counts rows as a proxy for volume, because the data has no per-row size. Honest.

- **(2)** The **ranking**: HV-HOST-01 first with about 37 percent of all Perf rows.

- **(3)** Suggestions to go deeper (the host's counters, a time series, a comparison with the previous day).

> **What you should see:** HV-HOST-01 about **36.7 %**, SQL2019-GUEST about **22 %**, RHEL94-GUEST about **12 %**, and the three Windows guests about **9.7 %** each. The host sends the most because it has the Hyper-V counters of all guests.

> **Be honest:** "We checked the agent's numbers against the raw data from the command line (below). They match **exactly**. The agent did not invent them. It ran real queries on our workspace and showed us which."

### Verify with PowerShell (optional, 1 minute)

> **Where to run it:** **Operator PC → Windows PowerShell**. `$SUB`, `$RG` and `$WS` as in Scene 2.

**The same two questions, asked directly**

```powershell
$KQL = "Usage | where TimeGenerated > ago(24h) | summarize MB = round(sum(Quantity),2) by DataType | order by MB desc"
az monitor log-analytics query --workspace $WS --analytics-query $KQL --query "[].{Table:DataType, MB:MB}" -o table
$KQL2 = "Perf | where TimeGenerated > ago(24h) | summarize Rows = count() by Computer | order by Rows desc"
az monitor log-analytics query --workspace $WS --analytics-query $KQL2 --query "[].{Computer:Computer, Rows:Rows}" -o table
```

> **What you should see:** The first table lists Perf at about 227 MB, then Heartbeat, Event and the two custom tables. The second lists HV-HOST-01 first, then SQL2019-GUEST, RHEL94-GUEST and the three Windows guests.

> **Beginner tip:** **You can also ask the agent about your own query.** Run a query in Logs first, then open the agent. It offers to use your last query: "interpret it, troubleshoot it or refine it".

> **Good to know:** The **same chat that explains the data also shows where the data volume comes from**, and you can ask the next question without leaving the page.

## 8B.6 Scene 4 – Investigate an alert (5 minutes, 4 of them waiting)

> **Say this:** "Now the real test. An alert fired on the recording day at 2:46 in the afternoon, local time. In Act 6 we saw it fire. Let us ask the agent: **what happened, and what should we do?** And, as always, we will check the answer."

> **Where to run it:** **Azure Portal**, on the **Alert details** page of the recorded alert (the page that has the **Investigate** button; see the link you prepared in 8B.1).

> **If something goes wrong:** **Use your saved link for the Alert details page.** The older alert page (the one Act 6 opens) does not have an **Investigate** button. Do not open the subscription-wide alert list on the projector: it shows unrelated alerts.

> **Do this:** Open the **Alert details** page. Read **Severity** (2 – Warning), **Fired time** (2:46 PM local time, which is 07:46 UTC), **Affected resource** (law-arc-monitor-lab) and **Alert condition** (Resolved). Read the box "**Why did this alert fire?**": the value was **463,277** and the threshold **110,000** (nanoseconds of wait per dispatch). At the top right, click **Investigate** (it has a green "New" label).

The alert details page shows these parts in reading order:

- **(1)** The **Investigate** button.

- **(2)** The alert's own facts: severity, fired time, affected resource, condition.

- **(3)** "**Why did this alert fire?**": 463,277 against a threshold of 110,000.

- **(4)** "View results in Logs": the alert's own query, for the engineer who wants to see it.

A new page opens: **Investigation: hv-cluster-contention-high**. The agent first **tells you its plan** and asks whether to begin. The plan page shows these parts in reading order:

- **(1)** The page title and the alert it was started from.

- **(2)** The **plan**: look at the 2 hours before **07:46 UTC**, the alert, the workspace, and related guests WIN2019-GUEST, WIN2022-GUEST and WIN2025-GUEST-01.

- **(3)** **Start investigation** – the button to begin.

- **(4)** Alternatives: add another resource, or focus on specific data.

- **(5)** "**Temporary chat**" – nothing is saved.

> **Be honest:** "Read the plan. It picked the correct time window (07:46 UTC is 14:46 local time, UTC+7) and the correct guests by itself. One sentence – 'mitigate the request failures' – is a **stock phrase**. This is a CPU wait alert, not a request failure. We note that, and we keep reading critically."

> **Do this:** Click **Start investigation**. Do **not** click anything else. The agent works for about **4 minutes** (3 minutes 46 seconds in the reference run). Use the talk track below while you wait.

> **Say this:** "While it works, let me say what it is doing. It plays the detective's routine: first it frames the problem – which resources, which hour. Then it collects metrics, logs, events and changes. Then it looks for what moved at the same time, in the same place and of the right kind. And, very important, it tries explanations and **rules out the weak ones**. We will see what it ruled out."

While the agent works, its steps are visible:

- **(1)** Its first checks looked at the **wrong dates** (a period before this workspace had data) and found nothing.

- **(2)** The count: "tables with data: 0". It then **corrected itself** and found the real window (07:41–07:56 UTC). Same as a human who first opens the wrong folder.

- **(3)** "Starting investigation process – Initializing…". The long wait is normal.

- **(4)** The **Stop** button. Do not press it.

> **Beginner tip:** **While you wait** you can tell the three facts about the Observability Agent: it uses **your** permissions (it cannot see what you cannot see); its work is a **temporary chat** unless you choose to save it; and its usage is **billed by use** (a deep investigation has a documented upper limit per run).

When it is finished, a **report panel** opens on the right. First look at the whole screen. The investigation report shows these parts in reading order:

- **(1)** **Create Issue** – saves the investigation as a record in an Azure Monitor workspace. **We never click it in this demo.** It changes Azure.

- **(2)** **Download report** – not used in this demo (we did not test it).

- **(3)** **Guest wait spike**: three lines jump together at **14:45 (local time)**. The text of the report says **07:45 UTC** – the same moment shown in two time zones.

- **(4)** **Pre vs incident**: bars compare the wait before and during the incident.

- **(5)** A second **Create Issue**, small, in the chat. Also **never click**.

> **Do this:** In the report panel click **Summary** to open it. Read **What happened**, **Analysis** and **What can be done next**.

The summary of the report, in plain words, shows these parts in reading order:

- **(1)** **What happened**: "host-level Hyper-V CPU scheduling contention on HV-HOST-01", driven by a sharp spike in **CPU Wait Time Per Dispatch**.

- **(2)** **Analysis**: baseline 17–34 thousand, then hundreds of thousands at 07:45 UTC; peaks 898 thousand (WIN2019-GUEST) and 894 thousand (WIN2022-GUEST); the **heartbeat continued** so the host was not down; **no change before the spike**; **the upstream initiator remains unknown**.

- **(3)** **What can be done next**: reduce or move the load, throttle the busiest guests, verify recovery, tune alerts.

- **(4)** **Create Issue** again – **do not click**.

### Grade the report – this is the heart of the scene

Do not just read the report aloud. **Grade it against the answer key.** We checked every claim against the raw data and the Activity Log:

| **What the agent said** | **What the evidence says** | **Verdict** |
|---|---|---|
| Alert fired because the host showed extreme wait; three Windows guests affected | The first minute above 100,000 ns is **07:45 UTC** for WIN2019-GUEST, WIN2022-GUEST and WIN2025-GUEST-01. The two light guests stayed much lower: SQL2019-GUEST peaked at 121 thousand (above 100 thousand only from 07:48) and RHEL94-GUEST at 77 thousand. | **Correct** |
| Baseline 17–34 thousand ns | Measured baseline 16,857–34,426 ns | **Correct** |
| Peaks 898 thousand (WIN2019) and 894 thousand (WIN2022) | Measured 898,238 and 893,908 ns | **Correct** |
| Heartbeat continued, so it was not an outage | Heartbeats present every 5 minutes | **Correct** |
| No aligned alert or health event found | **14 other alert instances (7 other rules)** fired between 07:50 and 08:01 UTC | **Incomplete** – fixed by the follow-up below |
| No change before the spike; only Arc run-command activity after | Activity Log: nothing before 08:18 UTC. Run-command and a few network and VM writes at 08:18–08:29 UTC, all **after** the spike | **Correct on the main point**, incomplete on detail |
| Root cause: CPU contention on the host; the upstream initiator is unknown | True. In our lab **we started the CPU load on purpose**. In real life "who started the load?" is the next question for the engineer, and the agent cannot see inside the guests. | **Correct, and honest** |
| Next steps: reduce or move load, verify, tune alerts | Sensible, general advice | **Reasonable** |

### Close the gap with one follow-up question

> **Do this:** In the box at the bottom of the chat type: `Were other alert rules in this workspace fired in the 20 minutes after <ALERT_FIRED_UTC>? Please list them with their fired times.` (Replace the placeholder as described in 8B.1.) Press **Enter** and wait about **35 seconds**.

The follow-up fills the gap: seven more alert rules. The answer shows these parts in reading order:

- **(1)** Your follow-up question.

- **(2)** "Reasoned for 0.57 minutes".

- **(3)** The list: **hv-guest-contention-high** four times from 07:50:03, **hv-cluster-cpu-high** 07:55:27, **hv-host-cpu-high** 07:56:16, **hv-host-cpu-critical** 07:57:25, **hv-cluster-cpu-critical** 07:59:13, **hv-guest-cpu-high** three times from 08:00:34 and **hv-guest-cpu-critical** three times from 08:01:40.

### Check the alert list yourself (PowerShell)

> **Where to run it:** **Operator PC → Windows PowerShell**. `$SUB` and `$RG` as in Act 0.

**Alerts that fired 07:40–08:10 UTC on the recording day** (replace `<INCIDENT_DATE>` with the date of the recording in the form `YYYY-MM-DD`)

```powershell
az rest --method get --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.AlertsManagement/alerts" `
  --uri-parameters "api-version=2019-05-05-preview" "timeRange=30d" "targetResourceGroup=$RG" "pageCount=250" "sortBy=startDateTime" "sortOrder=asc" `
  --query "value[?contains(properties.essentials.startDateTime,'<INCIDENT_DATE>T07:4') || contains(properties.essentials.startDateTime,'<INCIDENT_DATE>T07:5') || contains(properties.essentials.startDateTime,'<INCIDENT_DATE>T08:0')].{Rule:name, Start:properties.essentials.startDateTime, Condition:properties.essentials.monitorCondition}" -o table
```

> **What you should see:** **15 rows**: the original `hv-cluster-contention-high` at 07:46:00, then the other rules at 07:50:03 to 08:01:40 – the same list as the agent's, to the second. All are "Resolved".

> **Say this:** "The first report missed seven alert rules. One follow-up question fixed it. And **we knew** it was incomplete, because we had the answer key. **AI proposes, evidence disposes.** With an AI that shows its work, a mistake costs us a minute. Without one, it could cost us the trust of the whole team."

> **Do this:** **Leave the investigation without saving.** Click the **X** at the top right of the page. Azure asks: "**This conversation and its data will be permanently deleted. If you've run an investigation, cancel and create an issue to save the results.**" Click **OK**. You are back in the Portal. Nothing was created in Azure.

> **Be honest:** "This is a **temporary chat**. I closed it without creating an issue, so nothing was saved and nothing changed in your environment. If you want to keep an investigation, you can create an **Azure Monitor issue** – we do not do that in a demo, because it writes to your environment."

> **If something goes wrong:** **The agent may say different words** in your run. Judge it by the **answer key** (the table above and Appendix F), not by the exact sentences. **If the investigation does not start or takes more than 8 minutes**, say so, press nothing, and show the recorded results of this scene (the table above) instead. If the page says the service has a problem, refresh the page and start again once.

> **Good to know:** For this scene, four questions help you judge **any** AI assistant: (1) Does it show me the **steps and queries** it ran? (2) Does it tell me what it **could not** check? (3) Can it change things **without my approval**? (4) Can I **rerun** what it did, with my own tools? Here the answers are: yes, yes ("the upstream initiator remains unknown"), no, and yes (KQL and the CLI).

## 8B.7 Scene 5 (optional) – Ask the Troubleshooting Agent about the host disk (2 minutes)

Use this scene only if you have the time **and** an audience that is interested in storage. Its value is the **guided flow**, not the final sentence – and you must say so.

> **Say this:** "In Act 4 we saw that our storage test did not saturate the disk. Let us ask a **second** AI helper, the Troubleshooting Agent, the same question for the **Azure layer** of the host virtual machine."

> **Where to run it:** **Azure Portal** → search box → `HV-HOST-01` → choose the search result of type **Virtual machine** (not the one of type **Machine – Azure Arc**). Click **Copilot** in the header.

> **If something goes wrong:** The virtual machine page may show an **orange banner** about the VM agent. It is **unrelated** to this scene (we have not investigated it). Do not click it. The monitoring in this lab arrives through the **Azure Arc** machine, not through that banner.

> **Do this:** In the Copilot pane click the **arrow** next to **New chat** and choose **Troubleshooting** (see the helper menu in 8B.2). Type: `Why is the data disk of this VM slow? The slowness started on <TEST_DATE> at about <SLOW_START_LT> local time (UTC+7) and lasted until about <SLOW_END_LT>.` (Replace the placeholders as described in 8B.1.) Press **Enter**. A page **Select disks** opens. It lists **only this VM's disks** ("Showing 2 of 2"). Tick **HV-HOST-01-data** and click **Select**.

The agent asks which disk to examine. The page shows these parts in reading order:

- **(1)** Your question.

- **(2)** The **list of disks**: only the two disks of **this** VM, **HV-HOST-01-data** and **HV-HOST-01-osdisk**.

- **(3)** Tick **HV-HOST-01-data**: the 512 GB disk that holds the guests' virtual disks.

- **(4)** "**Showing 2 of 2**" – the list is scoped to this VM, not to the whole subscription.

- **(5)** The **Select** button (it becomes active after you tick a disk).

> **Do this:** Copilot asks when you saw the problem. Click **I have an exact time**. A **Start / End** form opens (local time). Set **Start** to the recording day at **11:30 AM** and **End** to the same day at **12:00 PM**, then click **Submit**. (The time list moves in 30-minute steps, so we take the half hour that contains 11:44–11:52 LT.)

The time form shows these parts in reading order. Times are in your local time zone:

- **(1)** The choice "**I have an exact time**".

- **(2)** A reminder: "**Enter times in your local time zone**".

- **(3)** The **Start and End** fields: date and time.

- **(4)** **Submit**.

> **Do this:** Copilot shows what it **will** do. Read it. Click **Yes, analyze my disks**. Wait about **1 minute**.

The plan and the request for consent show these parts in reading order:

- **(1)** The **resource and disk** that will be examined.

- **(2)** The **metrics** it will analyse: disk IOPS and bandwidth consumed, and the same at VM level (uncached and cached).

- **(3)** How: **1-minute intervals**, in the time period you gave, to find out whether a **disk or VM limit** was hit.

- **(4)** **Yes, analyze my disks** – you give consent. **No thanks** is also offered.

The answer in the reference run was general guidance. It shows these parts in reading order:

- **(1)** Three **common causes** of slow disks, with advice.

- **(2)** Links to Microsoft articles.

- **(3)** Follow-up suggestions.

> **Be honest:** "In the reference run the answer was **general advice**: three common causes and links. It did **not** say 'no limit was reached'. So I will check that myself, with the real Azure numbers – and you should never promise a verdict from this helper."

> **Do this:** Check the **answer key** from PowerShell (below).

> **Where to run it:** **Operator PC → Windows PowerShell**. `$SUB` and `$RG` as in Act 0.

**How close to its limit did the data disk get?** (replace `<INCIDENT_DATE>` with the date of the recording in the form `YYYY-MM-DD`)

```powershell
$VM = "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/HV-HOST-01"
$v = az monitor metrics list --resource $VM --metric 'Data Disk IOPS Consumed Percentage' --start-time <INCIDENT_DATE>T04:30:00Z --end-time <INCIDENT_DATE>T05:00:00Z --interval PT1M --aggregation Maximum --query "value[0].timeseries[0].data[].maximum" -o tsv
($v | Where-Object { $_ -ne '' } | Measure-Object -Maximum).Maximum
```

> **What you should see:** **35**: the data disk never used more than **35 percent** of its IOPS allowance (about 800 of 2,300). Bandwidth peaked at 10 percent and the virtual-machine limits at 6 percent or less. **Nothing was throttled at the Azure level.** This agrees with Act 4.

> **Say this:** "So the Azure layer was fine. And remember: this helper sees the **Azure** layer only – the virtual machine and its disk. What happens **inside** the nested guests we saw in the Workbook, layer by layer. The two tools do not compete; they answer different layers."

> **Beginner tip:** The Troubleshooting Agent can also offer to **create a support request**. We never click that in a demo.

## 8B.8 What comes next – talk track only (2 minutes, no clicking)

People always ask "and what about the future?" Use this table. **Do not demonstrate these items.** Most are in preview or need design work. The contents of this table come from Microsoft documentation as it was when this guide was written; check the current documentation before you quote a status, a region or a number.

| **Capability** | **What it is** | **Status and limits** | **In this demo** |
|---|---|---|---|
| **Autonomous operations** of the Observability Agent | A background agent that groups related alerts into **one Azure Monitor issue**, writes the "why they belong together" text and can run an investigation by itself. It makes **no changes**: people decide. | **Preview.** Needs a separate **Observability Agent resource** and is built around **Application Insights** applications. The agent is available only in the regions listed in the documentation; check that your workspace's region is supported. Billing for its automatic investigations has started. | Not shown |
| **Azure Monitor issues** | A saved record of an incident: summary, investigations, related alerts and resources. Can notify through action groups (e-mail, Logic Apps, Event Hubs, webhook to ServiceNow). | Preview. Stored in an Azure Monitor workspace. Needs the right Azure role to create. | **Not created** |
| **Azure SRE Agent** | A **separate product** that connects to incident tools (Azure Monitor, PagerDuty, ServiceNow), code repositories and can act in "Review" or "Autonomous" mode. | Billed by an always-on charge plus usage. Hosted in a few regions (Sweden Central, East US 2, Australia East) but can look at resources in any region. | Not shown |
| **Governance** | The agents use **your** permissions (Azure role-based access control). Administrators can switch agents on or off in the **Azure Copilot admin center**. Prompts and answers are kept up to **30 days**. Microsoft states that your data is **not used to train** the models. | The Observability Agent is a **global service**. If you have data-location requirements, **check where the processing happens** in Microsoft's documentation or with Microsoft. A chat cannot continue after 24 hours. Customer-managed keys are not supported for its conversations. Best in English. | Explained |
| **Cost** | Azure Copilot and the Troubleshooting Agent: **included**. Observability Agent: **Azure Agent Credits**, consumed by chat and by investigations. | The documented upper limit for one deep investigation is 300 credits in one article and 500 in another – **check the current number** before you quote it. See the price on the Azure Monitor pricing page. | Scene 4 used one investigation |

> **Be honest:** "Some of these parts are **previews**. They are useful today for **chat and investigation**. The **autonomous** part is something to design carefully, with your own alert rules and your own applications, before you rely on it."

## 8B.9 If something goes wrong in this act

| **What you see** | **What to do** |
|---|---|
| The **Copilot** button says you are not authorised, or the pane never opens | Do not fix it on stage. Say "Copilot access is controlled by the tenant administrator". Show the **recorded results** of this act (the answer tables of the scenes and Appendix F) and run the **saved queries of Appendix F** in the Logs editor. |
| Copilot takes longer than **90 seconds** | Wait. If it is still working after 2 minutes, press **Stop**, and paste the saved query from Appendix F. |
| Copilot's query differs from this guide | Normal. Compare **table and counter names** with the answer key. If they differ, paste the saved query. |
| Copilot lists machines from **other projects** | Close the pane at once. Say "this is why we name the resource group". Retry with the resource group in the sentence. |
| Observability Agent shows "a problem with OpenAI" | Refresh the page and start again once. If it fails again, show the recorded results. |
| No **Investigate** button on the alert page | You are on the older alert page. Open the **Alert details** page with the link you prepared in 8B.1. |
| The dialog "**This conversation and its data will be permanently deleted…**" appears | It is expected when you leave a temporary chat. Click **OK**. Do **not** click Create Issue. |
| Recorded data returns **no results** (the recording is older than 30 days) | The 30-day retention removed it. Use the **last 24 hours** prompts of Appendix F. |

## 8B.10 Closing sentence of Act 8B

> **Say this:** "Three things to remember. **One:** anybody can now ask in their own words. **Two:** the AI shows its work, and we check it against evidence – it was right on the numbers, it needed one follow-up to be complete, and it said honestly what it could not know. **Three:** nothing changed in your environment, and nothing will, without a person deciding."
