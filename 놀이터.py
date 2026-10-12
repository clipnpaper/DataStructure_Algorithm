import vis

A = [5, 3, 8, 1]
print("안녕하세요, 자료구조!")
vis.show(vis.array(A), note="처음 리스트")
A.sort()
vis.show(vis.array(A, hl={0: 'ok', 3: 'ok'}), note="정렬 후: 가장 작은 값과 가장 큰 값을 초록색으로")
print("정렬:", A)

vis.play()  # 지금까지 쌓은 장면을 브라우저 창에 애니메이션으로 띄운다