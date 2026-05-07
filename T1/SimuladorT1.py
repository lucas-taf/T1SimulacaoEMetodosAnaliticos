import yaml
from collections import defaultdict

class GeradorAleatorio:
    def __init__(self, semente):
        self.a = 1103515245
        self.c = 12345
        self.M = 2**31
        self.previous = semente
        self.usados = 0

    def next_random(self):
        if self.usados >= 100000:
            return None
        self.previous = (self.a * self.previous + self.c) % self.M
        self.usados += 1
        return self.previous / self.M


class Fila:
    def __init__(self, id_fila, servidores, capacidade=None, intervalo_servico=None, intervalo_chegada=None):
        self.id = id_fila
        self.servidores = servidores
        self.capacidade = capacidade if capacidade != float('inf') else None
        self.intervalo_chegada = intervalo_chegada
        self.intervalo_servico = intervalo_servico

        self.estado_atual = 0
        self.perdas = 0
        
        self.tempos_estados = defaultdict(float)

    def registrar_tempo_estado(self, delta_tempo):
        self.tempos_estados[self.estado_atual] += delta_tempo


class RedeFilasSimulador:
    def __init__(self, config, semente):
        self.rng = GeradorAleatorio(semente)
        self.tempo_global = 0.0
        self.eventos = []

        self.filas = {}
        for id_fila, dados in config["filas"].items():
            self.filas[id_fila] = Fila(
                id_fila=id_fila,
                servidores=dados["servidores"],
                capacidade=dados.get("capacidade", None),
                intervalo_servico=dados["servico"],
                intervalo_chegada=dados.get("chegada")
            )

        self.roteamento = config["roteamento"]

    def ordenar_eventos(self):
        prioridade = {"SAIDA": 0, "CHEGADA": 1}
        self.eventos.sort(key=lambda e: (e[0], prioridade[e[1]]))

    def agendar_evento(self, tempo, tipo, fila_id):
        self.eventos.append((tempo, tipo, fila_id))
        self.ordenar_eventos()

    def sortear_intervalo(self, minimo, maximo):
        rnd = self.rng.next_random()
        if rnd is None:
            return None
        return minimo + (maximo - minimo) * rnd

    def agendar_chegada_externa(self, fila_id):
        fila = self.filas[fila_id]
        if fila.intervalo_chegada is None:
            return

        intervalo = self.sortear_intervalo(*fila.intervalo_chegada)
        if intervalo is None:
            return

        novo_tempo = self.tempo_global + intervalo
        self.agendar_evento(novo_tempo, "CHEGADA", fila_id)

    def agendar_saida(self, fila_id):
        fila = self.filas[fila_id]

        tempo_servico = self.sortear_intervalo(*fila.intervalo_servico)
        if tempo_servico is None:
            return

        novo_tempo = self.tempo_global + tempo_servico
        self.agendar_evento(novo_tempo, "SAIDA", fila_id)

    def proximo_destino(self, fila_id):
        destinos = self.roteamento.get(fila_id, [])
        if not destinos:
            return None

        rnd = self.rng.next_random()
        if rnd is None:
            return None

        acumulado = 0.0
        for destino, prob in destinos:
            acumulado += prob
            if rnd <= acumulado:
                return destino

        return None

    def next_event(self):
        if self.eventos:
            return self.eventos.pop(0)
        return None

    def atualizar_estatisticas(self, novo_tempo):
        delta_tempo = novo_tempo - self.tempo_global
        for fila in self.filas.values():
            fila.registrar_tempo_estado(delta_tempo)
        self.tempo_global = novo_tempo

    def tratar_chegada(self, fila_id, gerar_proxima_externa=False):
        fila = self.filas[fila_id]

        if gerar_proxima_externa:
            self.agendar_chegada_externa(fila_id)

        
        if fila.capacidade is None or fila.estado_atual < fila.capacidade:
            fila.estado_atual += 1
            if fila.estado_atual <= fila.servidores:
                self.agendar_saida(fila_id)
        else:
            fila.perdas += 1

    def tratar_saida(self, fila_id):
        fila = self.filas[fila_id]

        if fila.estado_atual > 0:
            fila.estado_atual -= 1

        destino = self.proximo_destino(fila_id)

        if fila.estado_atual >= fila.servidores:
            self.agendar_saida(fila_id)

        if destino is not None:
            self.agendar_evento(self.tempo_global, "CHEGADA", destino)

    def executar(self, primeira_chegada_fila1):
        self.agendar_evento(primeira_chegada_fila1, "CHEGADA", 1)

        while self.eventos and self.rng.usados < 100000:
            evento = self.next_event()
            if evento is None:
                break

            tempo_evento, tipo_evento, fila_id = evento
            self.atualizar_estatisticas(tempo_evento)

            if tipo_evento == "CHEGADA":
                gerar_proxima_externa = (
                    fila_id == 1 and self.filas[fila_id].intervalo_chegada is not None
                )
                self.tratar_chegada(fila_id, gerar_proxima_externa=gerar_proxima_externa)

            elif tipo_evento == "SAIDA":
                self.tratar_saida(fila_id)

    def exibir_relatorio(self):
        print("=" * 50)
        print("RELATÓRIO DA REDE DE FILAS - T1")
        print("=" * 50)

        for fila_id in sorted(self.filas.keys()):
            fila = self.filas[fila_id]
            cap_str = fila.capacidade if fila.capacidade is not None else "Infinita"
            print(f"\nFila {fila_id}: G/G/{fila.servidores}/{cap_str}")
            print("-" * 40)
            print("Estado |   Tempo Total   | Probabilidade")

            tempo_total = sum(fila.tempos_estados.values())
            estados_max = max(fila.tempos_estados.keys()) if fila.tempos_estados else 0

            for estado in range(estados_max + 1):
                tempo = fila.tempos_estados.get(estado, 0.0)
                prob = (tempo / tempo_total) * 100 if tempo_total > 0 else 0
                print(f"  {estado:<6} | {tempo:15.4f} |  {prob:7.2f}%")

            print("-" * 40)
            print(f"Perdas da fila {fila_id}: {fila.perdas}")

        print("\n" + "=" * 50)
        print(f"Tempo global da simulação: {self.tempo_global:.4f}")
        print(f"Quantidade de aleatórios usados: {self.rng.usados}")
        print("=" * 50)

if __name__ == "__main__":
    with open("modelo.yml", "r") as arquivo:
        conteudo = arquivo.read()
        conteudo = conteudo.replace("!PARAMETERS", "")
        config_yaml = yaml.safe_load(conteudo)

    config_T1 = {"filas": {}, "roteamento": {}}
    
    for fila_id, dados in config_yaml["queues"].items():
        capacidade = dados.get("capacity", float('inf'))
        chegada = (dados["minArrival"], dados["maxArrival"]) if "minArrival" in dados else None
        servico = (dados["minService"], dados["maxService"])
        
        config_T1["filas"][fila_id] = {
            "servidores": dados["servers"],
            "capacidade": capacidade,
            "chegada": chegada,
            "servico": servico
        }

    for rota in config_yaml.get("network", []):
        origem = rota["source"]
        destino = rota["target"]
        probabilidade = rota["probability"]
        
        if origem not in config_T1["roteamento"]:
            config_T1["roteamento"][origem] = []
        config_T1["roteamento"][origem].append((destino, probabilidade))

    fila_inicial = list(config_yaml["arrivals"].keys())[0]
    tempo_inicial = config_yaml["arrivals"][fila_inicial]
    
    semente_usada = config_yaml["seeds"][0] if "seeds" in config_yaml else 42

    simulador = RedeFilasSimulador(config=config_T1, semente=semente_usada)
    simulador.executar(primeira_chegada_fila1=tempo_inicial)
    simulador.exibir_relatorio()