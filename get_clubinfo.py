import re
import time
import pandas as pd
import requests
import csv
from bs4 import BeautifulSoup

HTML_SNIPPET = r"""
<li><span class="num">1. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=1">부산클럽</a></li>
		<li><span class="num">2. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=2">북부산클럽</a></li>
		<li><span class="num">3. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=3">남부산클럽</a></li>
		<li><span class="num">4. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=4">동부산클럽</a></li>
		<li><span class="num">5. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=5">새부산클럽</a></li>
		<li><span class="num">6. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=6">센트랄클럽</a></li>
		<li><span class="num">7. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=7">동래클럽</a></li>
		<li><span class="num">8. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=8">서부산클럽</a></li>
		<li><span class="num">9. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=9">영도클럽</a></li>
		<li><span class="num">10. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10">대연클럽</a></li>
		<li><span class="num">11. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=11">뉴부산클럽</a></li>
		<li><span class="num">12. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=12">중부산클럽</a></li>
		<li><span class="num">13. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=13">제일클럽</a></li>
		<li><span class="num">14. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=14">부산진클럽</a></li>
		<li><span class="num">15. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=15">오륙도클럽</a></li>
		<li><span class="num">16. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=16">서면클럽</a></li>
		<li><span class="num">17. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=17">대하클럽</a></li>
		<li><span class="num">18. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=18">등대클럽</a></li>
		<li><span class="num">19. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=19">동백클럽</a></li>
		<li><span class="num">20. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=20">광복클럽</a></li>
		<li><span class="num">21. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=21">화랑클럽</a></li>
		<li><span class="num">22. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=23">양지클럽</a></li>
		<li><span class="num">23. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=24">대양클럽</a></li>
		<li><span class="num">24. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=25">남구클럽</a></li>
		<li><span class="num">25. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=26">아리랑클럽</a></li>
		<li><span class="num">26. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=27">구덕클럽</a></li>
		<li><span class="num">27. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=28">아세아클럽</a></li>
		<li><span class="num">28. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=29">현대클럽</a></li>
		<li><span class="num">29. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=30">로얄클럽</a></li>
		<li><span class="num">30. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=31">오대양클럽</a></li>
		<li><span class="num">31. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=32">연제클럽</a></li>
		<li><span class="num">32. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=33">반도클럽</a></li>
		<li><span class="num">33. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=34">육대주클럽</a></li>
		<li><span class="num">34. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=35">대교클럽</a></li>
		<li><span class="num">35. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=36">극동클럽</a></li>
		<li><span class="num">36. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=37">부산포클럽</a></li>
		<li><span class="num">37. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=38">해운대클럽</a></li>
		<li><span class="num">38. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=39">한륜클럽</a></li>
		<li><span class="num">39. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=40">부평클럽</a></li>
		<li><span class="num">40. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=41">복지클럽</a></li>
		<li><span class="num">41. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=42">낙동강클럽</a></li>
		<li><span class="num">42. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=43">부일클럽</a></li>
		<li><span class="num">43. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=44">용두클럽</a></li>
		<li><span class="num">44. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=45">동서클럽</a></li>
		<li><span class="num">45. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=46">고려클럽</a></li>
		<li><span class="num">46. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=47">동양클럽</a></li>
		<li><span class="num">47. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=48">문화클럽</a></li>
		<li><span class="num">48. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=49">금정클럽</a></li>
		<li><span class="num">49. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=50">무궁화클럽</a></li>
		<li><span class="num">50. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=51">충의클럽</a></li>
		<li><span class="num">51. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=52">사하클럽</a></li>
		<li><span class="num">52. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=54">한일클럽</a></li>
		<li><span class="num">53. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=55">대지클럽</a></li>
		<li><span class="num">54. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=56">금강클럽</a></li>
		<li><span class="num">55. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=57">태양클럽</a></li>
		<li><span class="num">56. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=58">삼미클럽</a></li>
		<li><span class="num">57. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=59">백란클럽</a></li>
		<li><span class="num">58. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=60">남촌클럽</a></li>
		<li><span class="num">59. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=61">평화클럽</a></li>
		<li><span class="num">60. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=62">기장클럽</a></li>
		<li><span class="num">61. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=63">송죽클럽</a></li>
		<li><span class="num">62. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=64">통일클럽</a></li>
		<li><span class="num">63. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=65">신라클럽</a></li>
		<li><span class="num">64. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=66">엑스포클럽</a></li>
		<li><span class="num">65. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=67">삼일클럽</a></li>
		<li><span class="num">66. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=68">백두산클럽</a></li>
		<li><span class="num">67. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=69">가야클럽</a></li>
		<li><span class="num">68. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=70">수란클럽</a></li>
		<li><span class="num">69. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=71">목화클럽</a></li>
		<li><span class="num">70. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=72">한빛클럽</a></li>
		<li><span class="num">71. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=73">사상클럽</a></li>
		<li><span class="num">72. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=74">자성대클럽</a></li>
		<li><span class="num">73. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=75">선명클럽</a></li>
		<li><span class="num">74. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=76">미소클럽</a></li>
		<li><span class="num">75. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=77">대주클럽</a></li>
		<li><span class="num">76. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=78">정심클럽</a></li>
		<li><span class="num">77. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=79">수영클럽</a></li>
		<li><span class="num">78. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=80">동남클럽</a></li>
		<li><span class="num">79. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=81">부경클럽</a></li>
		<li><span class="num">80. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=82">성보클럽</a></li>
		<li><span class="num">81. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=83">청라클럽</a></li>
		<li><span class="num">82. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=84">금명클럽</a></li>
		<li><span class="num">83. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=85">문명클럽</a></li>
		<li><span class="num">84. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=86">남포클럽</a></li>
		<li><span class="num">85. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=87">새천년클럽</a></li>
		<li><span class="num">86. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=88">장미클럽</a></li>
		<li><span class="num">87. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=89">21세기클럽</a></li>
		<li><span class="num">88. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=90">충렬클럽</a></li>
		<li><span class="num">89. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=91">백운포클럽</a></li>
		<li><span class="num">90. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=92">여명클럽</a></li>
		<li><span class="num">91. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=93">부영클럽</a></li>
		<li><span class="num">92. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=94">명륜클럽</a></li>
		<li><span class="num">93. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=96">롯데클럽</a></li>
		<li><span class="num">94. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=97">중앙클럽</a></li>
		<li><span class="num">95. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=98">비전클럽</a></li>
		<li><span class="num">96. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=99">무지개클럽</a></li>
		<li><span class="num">97. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=100">청룡클럽</a></li>
		<li><span class="num">98. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=101">대신클럽</a></li>
		<li><span class="num">99. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=102">남문클럽</a></li>
		<li><span class="num">100. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=103">고운클럽</a></li>
		<li><span class="num">101. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=104">자갈치클럽</a></li>
		<li><span class="num">102. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=105">수목클럽</a></li>
		<li><span class="num">103. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=106">다연클럽</a></li>
		<li><span class="num">104. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=107">혜성클럽</a></li>
		<li><span class="num">105. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=108">세종클럽</a></li>
		<li><span class="num">106. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=109">모티브PMJF클럽</a></li>
		<li><span class="num">107. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=110">에이원클럽</a></li>
		<li><span class="num">108. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=111">여원MJF클럽</a></li>
		<li><span class="num">109. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=112">누리마루클럽</a></li>
		<li><span class="num">110. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=113">삼성클럽</a></li>
		<li><span class="num">111. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=114">청록클럽</a></li>
		<li><span class="num">112. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=115">대명클럽</a></li>
		<li><span class="num">113. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=117">거송클럽</a></li>
		<li><span class="num">114. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=118">영광클럽</a></li>
		<li><span class="num">115. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=119">자유클럽</a></li>
		<li><span class="num">116. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=120">한마음클럽</a></li>
		<li><span class="num">117. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=122">미남클럽</a></li>
		<li><span class="num">118. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=123">대호클럽</a></li>
		<li><span class="num">119. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=125">금미해클럽</a></li>
		<li><span class="num">120. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=126">소명클럽</a></li>
		<li><span class="num">121. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=127">광명클럽</a></li>
		<li><span class="num">122. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=128">신우클럽</a></li>
		<li><span class="num">123. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=129">달음산클럽</a></li>
		<li><span class="num">124. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=130">대성클럽</a></li>
		<li><span class="num">125. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=131">골드클럽</a></li>
		<li><span class="num">126. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=133">하람클럽</a></li>
		<li><span class="num">127. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=134">우정MJF클럽</a></li>
		<li><span class="num">128. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=135">센텀PMJF클럽</a></li>
		<li><span class="num">129. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=137">미래클럽</a></li>
		<li><span class="num">130. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=138">정림클럽</a></li>
		<li><span class="num">131. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=139">금란클럽</a></li>
		<li><span class="num">132. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=145">장총클럽</a></li>
		<li><span class="num">133. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=146">해온클럽</a></li>
		<li><span class="num">134. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=147">파란클럽</a></li>
		<li><span class="num">135. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10000">울타리클럽</a></li>
		<li><span class="num">136. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10002">좋은클럽</a></li>
		<li><span class="num">137. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10003">마린비치클럽</a></li>
		<li><span class="num">138. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10004">아이블루클럽</a></li>
		<li><span class="num">139. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10005">드림클럽</a></li>
		<li><span class="num">140. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10006">해오름클럽</a></li>
		<li><span class="num">141. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10007">하모니클럽</a></li>
		<li><span class="num">142. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10008">레전드클럽</a></li>
		<li><span class="num">143. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10009">가람클럽</a></li>
		<li><span class="num">144. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10010">우일클럽</a></li>
		<li><span class="num">145. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10011">오션클럽</a></li>
		<li><span class="num">146. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10012">최강클럽</a></li>
		<li><span class="num">147. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10013">보담클럽</a></li>
		<li><span class="num">148. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10015">한누리클럽</a></li>
		<li><span class="num">149. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10017">퀸즈MJF클럽</a></li>
		<li><span class="num">150. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10018">클로버클럽</a></li>
		<li><span class="num">151. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10019">백향클럽</a></li>
		<li><span class="num">152. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10020">예스클럽</a></li>
		<li><span class="num">153. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10021">다사랑클럽</a></li>
		<li><span class="num">154. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10022">은하수클럽</a></li>
		<li><span class="num">155. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10023">모아클럽</a></li>
		<li><span class="num">156. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10024">아름다운클럽</a></li>
		<li><span class="num">157. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10025">동문클럽</a></li>
		<li><span class="num">158. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10026">아너스MJF클럽</a></li>
		<li><span class="num">159. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10027">빛나는클럽</a></li>
		<li><span class="num">160. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10028">은성클럽</a></li>
		<li><span class="num">161. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10029">새마음클럽</a></li>
		<li><span class="num">162. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10030">부산태영클럽</a></li>
		<li><span class="num">163. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10031">진명클럽</a></li>
		<li><span class="num">164. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10032">청연클럽</a></li>
		<li><span class="num">165. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10033">한울림클럽</a></li>
		<li><span class="num">166. </span><a class="cname" href="http://lc355a.or.kr/bbs/content.php?co_id=ready02&club_idx=10034">커리어클럽</a></li>
"""


BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}

TARGET_FIELDS = ["창립일자", "스폰서클럽", "창립회장", "창립회원수", "현재회원수"]

def clean_text(text):
    if text is None:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_links(html):
    pattern = r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    matches = re.findall(pattern, html, re.S)
    results = []
    for href, name in matches:
        results.append({
            "url": href.strip(),
            "club_name_from_list": clean_text(re.sub(r"<.*?>", "", name))
        })
    return results

def parse_club_page(html, url=""):
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "클럽명": "",
        "회장지침": "",
        "회장": "",
        "총무": "",
        "재무": "",
        "창립일자": "",
        "스폰서클럽": "",
        "창립회장": "",
        "창립회원수": "",
        "현재회원수": "",
        "url": url
    }

    # 클럽명
    club_name_tag = soup.select_one("div.club_name")
    if club_name_tag:
        club_name = clean_text(club_name_tag.get_text())
        club_name = re.sub(r"^\d+\.\s*", "", club_name)
        result["클럽명"] = club_name

    # 회장지침
    guide = soup.select_one("div.club_guide")
    if guide:
        spans = guide.find_all("span")
        if len(spans) >= 2:
            result["회장지침"] = clean_text(spans[1].get_text())
        else:
            guide_text = clean_text(guide.get_text())
            guide_text = re.sub(r"^회장지침\s*:\s*", "", guide_text)
            result["회장지침"] = guide_text

    # 연혁 정보
    info_dl = soup.select_one("div.club_his dl.info")
    if info_dl:
        dts = info_dl.find_all("dt")
        dds = info_dl.find_all("dd")

        for dt, dd in zip(dts, dds):
            key = clean_text(dt.get_text())
            val = clean_text(dd.get_text())
            if key in TARGET_FIELDS:
                result[key] = val

    # 클럽 3역
    role_divs = soup.select("ul.img_list li div")
    for div in role_divs:
        txt = clean_text(div.get_text())

        m = re.match(r"^(회장|총무|재무)\s+(.*)$", txt)
        if m:
            role = m.group(1)
            name = clean_text(m.group(2))
            result[role] = name

    return result

def fetch_page(url, session):
    resp = session.get(url, headers=BASE_HEADERS, timeout=20)
    resp.raise_for_status()

    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding

    return resp.text

def main():
    links = extract_links(HTML_SNIPPET)
    print(f"총 {len(links)}개 링크 발견")

    session = requests.Session()
    rows = []

    for idx, item in enumerate(links, start=1):
        url = item["url"]
        list_name = item["club_name_from_list"]
        print(f"[{idx}/{len(links)}] 수집 중: {list_name} -> {url}")

        try:
            html = fetch_page(url, session)
            row = parse_club_page(html, url=url)

            if not row["클럽명"]:
                row["클럽명"] = list_name

            rows.append(row)

        except Exception as e:
            rows.append({
                "클럽명": list_name,
                "회장지침": "",
                "회장": "",
                "총무": "",
                "재무": "",
                "창립일자": "",
                "스폰서클럽": "",
                "창립회장": "",
                "창립회원수": "",
                "현재회원수": "",
                "url": url,
                "error": str(e)
            })

        time.sleep(0.3)

    output_file = "club_info_extended.csv"
    fieldnames = [
        "클럽명",
        "회장지침",
        "회장",
        "총무",
        "재무",
        "창립일자",
        "스폰서클럽",
        "창립회장",
        "창립회원수",
        "현재회원수",
        "url",
        "error"
    ]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if "error" not in row:
                row["error"] = ""
            writer.writerow(row)

    print(f"완료: {output_file}")

if __name__ == "__main__":
    main()