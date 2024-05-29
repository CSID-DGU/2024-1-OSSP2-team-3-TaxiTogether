from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Tuple
import requests
import itertools

app = FastAPI()

class Coordinates(BaseModel):
    lat: float
    lon: float

class RequestModel(BaseModel):
    start: Coordinates
    points: Dict[str, Coordinates]

def get_distance_from_kakao_api(api_key, coord1, coord2):
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {
        "Authorization": f"KakaoAK {api_key}"
    }
    params = {
        "origin": f"{coord1[1]},{coord1[0]}",
        "destination": f"{coord2[1]},{coord2[0]}"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json()
        return result['routes'][0]['summary']['distance']
    else:
        raise Exception("Error fetching data from Kakao API")

def get_fare_from_kakao_api(api_key, coord1, coord2):
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {
        "Authorization": f"KakaoAK {api_key}"
    }
    params = {
        "origin": f"{coord1[1]},{coord1[0]}",
        "destination": f"{coord2[1]},{coord2[0]}"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json()
        fare_info = result['routes'][0]['summary']['fare']
        return fare_info['taxi'] + fare_info['toll']
    else:
        raise Exception("Error fetching data from Kakao API")

def calculate_percentage(a, b, c, d, k, l, n, M, x):
    t1 = a / 4 + k / 3 + l / 2 + n
    t2 = a / 4 + k / 3 + l / 2
    t3 = a / 4 + k / 3
    
    try:
        percentage1 = round((1 - (t1 - b / 4) / (3 * b / 4 + 3 * M / (4 * x))) * 100)
    except ZeroDivisionError:
        percentage1 = 0
    try:
        percentage2 = round((1 - (t2 - c / 4) / (3 * c / 4 + 3 * M / (4 * x))) * 100)
    except ZeroDivisionError:
        percentage2 = 0
    try:
        percentage3 = round((1 - (t3 - d / 4) / (3 * d / 4 + 3 * M / (4 * x))) * 100)
    except ZeroDivisionError:
        percentage3 = 0

    return percentage1, percentage2, percentage3

def calculate_distances(coords, api_key):
    distances = {}
    for i, j in itertools.combinations(coords, 2):
        dist = get_distance_from_kakao_api(api_key, coords[i], coords[j])
        distances[(i, j)] = dist
        distances[(j, i)] = dist
    return distances

def validate_availability(start, points, api_key):
    if len(points) < 2:
        raise ValueError("At least two destinations are required")
    
    M = 4800
    x = 100000 / 131
    
    points_with_start = {'start': start, **points}
    distances = calculate_distances(points_with_start, api_key)
    
    names = list(points.keys())
    
    best_route = None
    min_distance = float('inf')
    for perm in itertools.permutations(names):
        route_distance = distances[('start', perm[0])]
        for i in range(len(perm) - 1):
            route_distance += distances[(perm[i], perm[i+1])]
        route_distance += distances[(perm[-1], 'start')]
        
        if route_distance < min_distance:
            min_distance = route_distance
            best_route = perm
    
    a = distances[('start', best_route[0])]
    b = distances[('start', best_route[-1])]
    c = distances[('start', best_route[1])]
    d = distances[('start', best_route[2])] if len(best_route) > 2 else 0
    k = distances[(best_route[0], best_route[1])]
    l = distances[(best_route[1], best_route[2])] if len(best_route) > 2 else 0
    n = distances[(best_route[2], best_route[3])] if len(best_route) > 3 else 0
    
    percentages = calculate_percentage(a, b, c, d, k, l, n, M, x)
    
    result = {}
    for i, name in enumerate(best_route):
        if i == 0:
            result[name] = percentages[0]
        elif i == 1:
            result[name] = percentages[1]
        elif i == 2:
            result[name] = percentages[2]
        else:
            result[name] = 0

    return best_route, result

def calculate_each_fare(best_route, start, coords, api_key):
    num_points = len(best_route)
    
    if num_points == 2:
        p1 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) / 4
        p2 = get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) / 3 + p1
        p3 = p2

        q1 = get_fare_from_kakao_api(api_key, start, coords[best_route[1]])
        q2 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]])
        q3 = q2

        b1 = q2 / q1
        b2 = q2 / q2

        total_b = b1 + b2

        fare1 = p1 + p3 * b1 / total_b
        fare2 = p2 + p3 * b2 / total_b

        return {
            best_route[0]: fare1,
            best_route[1]: fare2
        }

    elif num_points == 3:
        p1 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) / 5
        p2 = get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) / 4 + p1
        p3 = get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]]) / 3 + p1 + p2
        p4 = p3

        q1 = get_fare_from_kakao_api(api_key, start, coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]])
        
        q2 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[2]])
        
        q3 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]])

        b1 = q3 / q1
        b2 = q3 / q2
        b3 = q3 / q3

        total_b = b1 + b2 + b3

        fare1 = p1 + p4 * b1 / total_b
        fare2 = p2 + p4 * b2 / total_b
        fare3 = p3 + p4 * b3 / total_b

        return {
            best_route[0]: fare1,
            best_route[1]: fare2,
            best_route[2]: fare3
        }

    elif num_points == 4:
        p1 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) / 5
        p2 = get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) / 4 + p1
        p3 = get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]]) / 3 + p1 + p2
        p4 = get_fare_from_kakao_api(api_key, coords[best_route[2]], coords[best_route[3]]) / 2 + p1 + p2 + p3
        p5 = p4

        q1 = get_fare_from_kakao_api(api_key, start, coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[2]], coords[best_route[3]])
        
        q2 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[2]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[2]], coords[best_route[3]])
        
        q3 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[3]])
        
        q4 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]])

        q5 = get_fare_from_kakao_api(api_key, start, coords[best_route[0]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[0]], coords[best_route[1]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[1]], coords[best_route[2]]) + \
             get_fare_from_kakao_api(api_key, coords[best_route[2]], coords[best_route[3]])

        b1 = q5 / q1
        b2 = q5 / q2
        b3 = q5 / q3
        b4 = q5 / q4

        total_b = b1 + b2 + b3 + b4

        fare1 = p1 + p5 * b1 / total_b
        fare2 = p2 + p5 * b2 / total_b
        fare3 = p3 + p5 * b3 / total_b
        fare4 = p4 + p5 * b4 / total_b

        return {
            best_route[0]: round(fare1),
            best_route[1]: fare2,
            best_route[2]: fare3,
            best_route[3]: fare4
        }

@app.post("/validate_route")
def validate_route(request: RequestModel):
    start = [request.start.lat, request.start.lon]
    points = {key: [point.lat, point.lon] for key, point in request.points.items()}
    api_key = "af3a07081f830adca6b60768135b5e54"

    try:
        result = validate_availability(start, points, api_key)

        is_available = True
        for value in result[1].values():
            if value != 0 and value < 60:
                is_available = False
                break

        if not is_available:
            raise HTTPException(status_code=400, detail="Invalid route: one or more points have less than 60% availability")

        fares = calculate_each_fare(result[0], start, points, api_key)
        return {"best_route": result[0], "fares": fares}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 코드를 실행하려면 다음 명령어를 실행해주세요: uvicorn main:app --reload